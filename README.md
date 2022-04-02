# Web Scraper for Reddit's CMV Delta Threads

[demo](reddit.ipynb)

This web scraper collects discussion threads that led to a change of someone's view to a certain topic.


## Setting up
1. Obtain your credentials by following [this](https://www.geeksforgeeks.org/scraping-reddit-using-python/).
2. Hard-code your credentials into `utils.py`.
```
def activate_reddit():
    client_id = "XXX"
    secret = "YYY"
    user_agent = "ZZZ"
    reddit = praw.Reddit(client_id=client_id, 
                         client_secret=secret, 
                         user_agent=user_agent)
    return reddit
```

3. Dependencies are listed in `requirements.txt`. 
```
pip3 install -r requirements.txt
```

4. The web browser is controlled by `Selenium` with `FireFox` driver.

### Troubleshooting
- If you cannot import `praw` to Python3 after installing the dependencies, try this:
```
pip3 install <package> --upgrade --force-reinstall
```
- For Mac user encountering the "WebDriverException: Message: 'geckodriver' executable needs to be in PATH," Run the following command to make geckodriver available to your system.
```
!brew install geckodriver
```
- If you still encounter the above error, install it manually.
1. Download geckodriver from the [source](https://github.com/mozilla/geckodriver/releases)
2. Copy geckodriver to folder `/usr/local/bin`

## Start scraping
For either starting anew or updating the existing corpus, run:
```
python3 reddit_scraper_pipeline.py --master_dir PATH_WHERE_PAST_DATA_IS_LOCATED --save_dir PATH_TO_SAVE_UPDATED_DATA
```
The path `master_dir` is where your current master data is located. The path `save_dir` is where you want to save updated master data. To scrape anew, run the above command without creating those directories; the scraper will automatically create them.

#### `master_dir` vs. `save_dir`

As a precausion, I recommend to avoid overwriting your master data when updating your corpus. For example, you can automatically maintain a backup copy of past data by specifying two different directories, one each for `master_dir` and `save_dir` like this:

Day 1: Specify the same directories for `master_dir` and `save_dir` as there are no past data.
```
python3 reddit_scraper_pipeline.py --master_dir feb25 --save_dir feb25
```

Day 2: For `master_dir`, specify the directory from Day 1. For `save_dir`, specify a new directory to avoid overwriting it.
```
python3 reddit_scraper_pipeline.py --master_dir feb25 --save_dir feb26
```

#### What is master data? 

Master data is comprised of:
- `submission.json`: contains topic submission data ("submission" = the root comment submitted to post a new discussion topic)
- `delta_thread.json`: contains a series of comments that eventually led to a change of perspective. That change is signified by `delta` signage. 
- `log.json`: keeps track of scraping progress. Even if scraping is interrupted by some error (lost connection, etc.), this file tells the scraper where to resume. This file also supports the scraper to avoid redundant processing for regular updates of the corpus.

## Scraping algorithm
1. Go to Reddit's [DeltaLog](https://www.reddit.com/r/DeltaLog/) to obtain a list of those Redditors whose comment(s) received "delta" ("delta receivers").
2. Compare that delta receivers list against our master list and update our list by adding new receivers. Based on that list, create `todo` list. In the example below, there are 86 delta receivers in the master and the scraper found 7 new delta receivers. After adding those 7 to our master, we have 93 delta receivers in the master as well as `todo`. 
```
Before: 86 delta receivers in total
7 delta receivers are added.
After: 93 delta receivers in total
Updated at: 2022-02-27 00:00:47
```
3. Pop one receiver from `todo`, go to that user's history page, and grab a list of comments that received "delta" ("delta comment").
4. Compare that user-specific list against our master and update the master by adding the new delta comment, along with all the comments within the same thread ("delta thread"). 

Case 1: While scraping delta threads, we often encounter [deleted] or [removed] comments. In the example below, the user -paperbrain- was given two new deltas but the second one contained a comment that was either deleted or removed. In such case, scraping is skipped.
```
-paperbrain- has got 2 new deltas.
Processing 0 ...
Processing 1 ...
Thread contains [deleted] parents. No comment is added.
```

Case 2: In the example below, the user Darq_At is already in our master with a history of receiving delta(s). This time around, the scraper does not find any delta that has newly given to this user since the previous scraping.
```
Darq_At has got 0 new deltas.
```

5. Each thread has a tree structure. So the scraper recursively grabs all the comments in the ancestry until it hits the root comment (called "submission" by Reddit). Each time the scraper finds a new, intact thread, it updates `delta_thread.json`. If that thread belongs to a submission that the scraper has never seen before, that submission is added to `submission.json`. If the new thread contains invalid comment(s), the scraper updates `log.json` to remember it as invalid thread so that next time it sees the same thread, it can skip it over.
6. Every time the scraper completes processing one delta receiver, add that receiver to active `done` list, and update both `todo` and `done` lists in `log.json`.
7. When `todo` is exhausted, terminate the scraping. Initialize `done` in `log.json` as an empty list. Flushes the report like this:
```
REPORT ----------------------------------------------------------------------
93 delta receivers
389 comments (including invalid/skipped ones)
Submission count: 1996 -> 2144
Thread count: 2207 -> 2374
Time elapsed: 75 minutes
Completed 2022-02-27 01:15:42
```

The next time the scraper is called, first grab `todo` and `done` from the log. If `todo` is not empty, then start from Step 3. If `todo` is empty, then start from Step 1.

## Filtering function
The filter can be applied by specifying keywords, such as "climate change." To do so, specify keywords in the `main` function call of `reddit_scraper_pipeline.py`.

## Prevention of data loss
To prevent data loss, each time one thread (a set of one submission post and its comments) is scraped, that thread is dumped in `submission.json` and `delta_thread.json`. 

## Prevention of redundant scraping
The scraping progress is controled by the fields within `log.json`: `delta_receivers`, `todo`, `done`, and `invalid_threads`. `todo` and `done` tell the scraper where to resume, even if scraping is interrupted by some error (lost connection, timeout, system error, etc.). `delta_receivers` remembers all the Reddit users the scraper has checked. `invalid_threads` remembers all the invalid the scraper has seen, thereby skipping them next time.
