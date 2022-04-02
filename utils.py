import praw

def activate_reddit():
    client_id = "XXX"
    secret = "YYY"
    user_agent = "ZZZ"
    reddit = praw.Reddit(client_id=client_id,
                         client_secret=secret,
                         user_agent=user_agent)
    return reddit