import argparse
import time, json, os
from collections import defaultdict

# custom script
import reddit_scraper as red

def main(args, keywords):
    "The pipeline for web-scraping the delta threads of Reddit."

    submission_dict, delta_thread_dict, log_dict = red.load_master(args.master_dir)
    start = time.time()
    before_submission_cnt = len(submission_dict['submission_id'])
    before_thread_cnt = len(delta_thread_dict)

    todo_list, done_list = log_dict['todo'], log_dict['done']
    if len(todo_list) == 0:
        # Go to Reddit DeltaLog and update our delta_receivers in the log
        log_dict = red.update_delta_receivers(log_dict)
        # Set the up-to-date list as todo_list
        todo_list = log_dict['delta_receivers'].copy()  # MUST BE A COPY
    print("Start processing", len(todo_list), "delta receivers")

    receiver_count, comment_count = 0, 0
    while todo_list:
        current = todo_list.pop()
        receiver_count += 1
        delta_links = red.get_delta_links(current)
        delta_links = red.drop_old_delta_links(delta_links, delta_thread_dict, log_dict)
        print(receiver_count, current, "has got", len(delta_links), "new deltas.")
        for i, link in enumerate(delta_links):
            print("Processing", i, "...")
            comment = red.get_delta_comment(link)
            if comment:
                submission_dict, delta_thread_dict, log_dict = red.add_delta_thread_to_master(
                                        comment, submission_dict, delta_thread_dict, 
                                        log_dict, keywords)
                red.save_master(args.save_dir, submission_dict, delta_thread_dict, log_dict)
                red.take_pause(1)
                comment_count += 1

        # Save the current state on the disk, every time one receiver is processed
        log_dict['todo'] = todo_list
        done_list.append(current)
        log_dict['done'] = done_list
        red.save_master(args.save_dir, submission_dict, delta_thread_dict, log_dict)

    # Wrapping up
    log_dict['todo'] = []
    log_dict['done'] = []
    red.save_master(args.save_dir, submission_dict, delta_thread_dict, log_dict)
    print("\nREPORT", "-"*70)
    print(receiver_count, "delta receivers")
    print(comment_count, "new comments (including invalid/skipped ones)")
    print("Submission count:", before_submission_cnt, "->", len(submission_dict['submission_id']))
    print("Thread count:", before_thread_cnt, "->", len(delta_thread_dict))
    print("Time elapsed:", int((time.time() - start)/60), "minutes")
    print("Completed", red.convert_timestamp(time.time()))


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--master_dir", required=True,
        help="The path to the master files (submission, delta_thread, log)",
    )
    parser.add_argument(
        "--save_dir", required=True,
        help="The path for saving the updated master files (submission, delta_thread, log)",
    )
    args = parser.parse_args()
    keywords = ['climate change']

    main(args, keywords)