import praw
#import pandas as pd
import requests, re, time, random, json, os
from bs4 import BeautifulSoup as bs
from collections import defaultdict
from datetime import datetime

# Selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
opts = Options()
opts.add_argument('--headless')  # headless mode

# Custom script
import utils

reddit = utils.activate_reddit()

def take_pause(interval):
    """Take pause for one second + randomness based on the given interval."""
    time.sleep(1 + interval*random.random())


def get_delta_comment(url):
    """Given an URL, return a Comment object."""
    regex = re.compile(r'.*/([\w]+)?\?context')
    mo = regex.search(url)
    if mo:
        return reddit.comment(id=mo.group(1))
    else:
        return None


def drop_old_delta_links(links, delta_thread_dict, log_dict):
    """Given a list of URLs, return a list that contains only new URLs."""
    new_links = []
    for link in links:
        regex = re.compile(r'comments/([\w]+)/')
        mo = regex.search(link)
        if mo:
            submission_id = mo.group(1)
        regex = re.compile(r'.*/([\w]+)?\?context')
        mo = regex.search(link)
        if mo:
            comment_id = mo.group(1)
        try:
            if submission_id and comment_id:
                key = f'{submission_id}-{comment_id}'
                if key in delta_thread_dict:
                    pass
                elif key in log_dict['invalid_threads']:
                    pass
                else:
                    new_links.append(link)
        except:
            pass

    return new_links


def add_delta_thread_to_master(
    comment, submission_dict, delta_thread_dict, log_dict, keywords):
    """Given a Comment object, do:
    1. Check it is NOT for the thread that already exists in the master.
    2. Collect the discussion thread fo the Comment.
    3. If the thread is valid,
         a. add it to the delta_thread master
         b. check if the thread's submission exists in the submission master;
            if not, add it to the master
       If the thread is invalid, record it in the log.
    
    Return updated submission_dict, delta_thread_dict, log_dict
    """
    submission_id = comment.submission.id
    delta_thread_key = f'{submission_id}-{comment.id}'
    if is_target(submission_id, keywords):
        if delta_thread_key in delta_thread_dict:
            pass
        else:
            thread = get_delta_thread(comment, [])
            if thread:
                delta_thread_dict[delta_thread_key] = thread
                if not submission_id in submission_dict['submission_id']:
                    submission_dict = add_submission(submission_id, submission_dict)
            else:
                log_dict['invalid_threads'].append(delta_thread_key)
                print("Thread contains [deleted] parents. No comment is added.")
    else:
        log_dict['invalid_threads'].append(delta_thread_key)
        print("Thread does not contain keywords. No comment is added.")    

    return submission_dict, delta_thread_dict, log_dict


def update_delta_receivers(log_dict):
    """Given the log, do:
    1. Go to the DeltaLog of Reddit
    2. Grab the list of receivers in their log
    3. Add new receivers to our log object & record the timestamp
    4. Save our log object to the disk
    Return the updated log
    
    Args:
        log_dict (dict) -- our log
    """
    # STEP 1
    print(f"Before: {len(log_dict['delta_receivers'])} delta receivers in total")
    url = "https://www.reddit.com/r/DeltaLog/"
    driver = webdriver.Firefox(options=opts)
    driver.get(url)
    timestamp = time.time()  # NOTE 1
    html = driver.find_element(By.TAG_NAME, 'html')
    html.send_keys(Keys.END)  
    take_pause(15)  # NOTE 2
    soup = bs(html.get_attribute('outerHTML'), "html.parser")  # NOTE 3
    driver.quit()
    
    # STEP 2
    new_list = [tag.a['href'] for tag in soup.find_all('p') if tag.text.startswith('1 delta from')]
    new_list = [receiver.split('/')[-2] for receiver in new_list]  # NOTE 4
    new_list = set(new_list)
    
    # STEP 3
    old_receivers = log_dict['delta_receivers']
    new_receivers = new_list.difference(set(old_receivers))
    log_dict['delta_receivers'].extend(list(new_receivers))
    log_dict['updated_utc'] = timestamp
    log_dict['updated_at'] = convert_timestamp(timestamp)
    
    # STEP 4
    with open('log.json', 'w') as f:
        json.dump(log_dict, f, indent=4)

    print(f"{len(new_receivers)} delta receivers are added.")
    print(f"After: {len(log_dict['delta_receivers'])} delta receivers in total")
    print(f"Updated at: {convert_timestamp(timestamp)}")
    
    return log_dict

    # NOTES
    # 1. Grab the timestamp
    # 2. Allow ample time for the system to process Keys.END
    # 3. https://stackoverflow.com/questions/53376789/how-to-pass-a-web-element-into-the-beautifulsoup
    # 4. '/u/Hellioning/' --> Hellioning


def save_master(save_dir, submission_dict, delta_thread_dict, log_dict):
    "Save the two master and one log files in save_dir."
    if not os.path.exists(save_dir):
        os.mkdir(save_dir)
        
    with open(os.path.join(save_dir, "delta_thread.json"), "w") as f:
        json.dump(delta_thread_dict, f, indent=4)

    with open(os.path.join(save_dir, "submission.json"), "w") as f:
        json.dump(submission_dict, f, indent=4)
        
    with open(os.path.join(save_dir, "log.json"), "w") as f:
        json.dump(log_dict, f, indent=4)


def load_master(master_dir):
    """Returns three master files present in `master_dir`. If such directory does
    not exist, create one and three master files, and then return them. 
    """
    if not os.path.exists(master_dir):
        os.mkdir(master_dir)
        create_new_master(master_dir)
        print("New master files are created.")
    
    with open(os.path.join(master_dir, 'submission.json'), 'r') as f:
        submission_dict = json.load(f)
    with open(os.path.join(master_dir, 'delta_thread.json'), 'r') as f:
        delta_thread_dict = json.load(f)
    with open(os.path.join(master_dir, 'log.json'), 'r') as f:
        log_dict = json.load(f)

    return submission_dict, delta_thread_dict, log_dict


def create_new_master(master_dir):
    """Create three new master files."""
    submission_dict, delta_thread_dict = defaultdict(list), defaultdict(list)
    log_dict = {
        "updated_at": time.time(),
        "delta_receivers": [],
        "todo": [],
        "done": [],
        "invalid_threads": [],
    }
    submission_dict = {
        'submission_id': [],
        'submission_author': [], 
        'submission_url': [], 
        'submission_title': [], 
        'submission_body': []
    }
    save_master(master_dir, submission_dict, delta_thread_dict, log_dict)


def get_delta_links(delta_receiver):

    # Get soup
    url = f"https://www.reddit.com/r/changemyview/wiki/user/{delta_receiver}"
    driver = webdriver.Firefox(options=opts)
    driver.get(url)
    soup = bs(driver.page_source, "html.parser")
    driver.quit()
    take_pause(2)
    
    # Extract the links
    links = []
    try:  # to address AttributeError: 'NoneType' object has no attribute 'find_all'
        delta_list = soup.find('table').find_all('td', attrs={'align': 'center'})
        if delta_list:
            for delta in delta_list:
                links += [a['href'] for a in delta.find_all('a') if a['href'].startswith('http')]
    except:
        pass

    return links


def add_submission(submission_id, submission_dict):
    """Given a submission ID, add details to the submission dictionary.
    
    Args:
        submission_id (str): The identifier of a submission.
    """
    submission = reddit.submission(id=submission_id)
    submission_dict['submission_id'].append(submission.id)
    submission_dict['submission_author'].append(submission.author.name)
    submission_dict['submission_url'].append(submission.url)
    submission_dict['submission_title'].append(submission.title)
    submission_dict['submission_body'].append(submission.selftext)
    
    return submission_dict


def convert_timestamp(timestamp):
    """Convert Unix Time into string type.
    
    Example:
        ts = 1645612795.0
        datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        --> <class 'str'> 2022-02-23 10:39:55
    """
    return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def format_comment(comment):
    """Given a comment object, return the comment in the corpus-format dictionary.
    
    Args:
        comment (praw.reddit.Comment class): Comment object.
    """
    comment_dict = {
        'comment_id': comment.id,
        'created_utc': comment.created_utc,  # used for collecting todo list
        'timestamp': convert_timestamp(comment.created_utc), 
        'author': comment.author.name, 
        'parent_id': comment.parent_id, 
        'comment': comment.body
    }
    
    return comment_dict


def get_delta_thread(comment, thread):
    """Given a comment object, go upwards along its ancestry. 
    If any ancester is [deleted], stop and return None. 
    If all ancesters are present, return a list of dicts 
    representing all the comments above the tree."""
    # Check invalid comment    
    INVALID_TAGS = ['[deleted]', '[removed]']
    submission = comment.submission
    if (submission.url is None) or (len(submission.url) < 15):
        return False
    if (submission.title is None) or (len(submission.title) < 15):
        return False
    if (submission.author is None) or (submission.author in INVALID_TAGS):
        return False
    if (submission.selftext is None) or (len(submission.selftext) < 15):
        return False
    elif (comment.author is None) or (comment.author in INVALID_TAGS):
        return False
    elif (comment.body is None) or (comment.body in INVALID_TAGS):
        return False
    else:
        # add the parent comment at the beginning
        thread.insert(0, format_comment(comment))
    
    # Check the stop condition
    if comment.is_root:
        return thread
    else:
        parent_id = comment.parent_id.split('_')[1]
        parent_comment = reddit.comment(parent_id)
        return get_delta_thread(parent_comment, thread)


def is_target(submission_id, keywords):
    """Given submission_id and a list of keywords, do:
    1. If the keyword list is empty, return True
    2. Otherwise, loop over the keyword list and return True if there is a match; 
       False otherwise
    """
    flag = False
    if len(keywords) == 0:
        flag = True
    else:
        submission = reddit.submission(id=submission_id)
        for keyword in keywords:
            if keyword.lower() in submission.title.lower():  # or (keyword in submission.selftext):
                flag = True
                break
    return flag