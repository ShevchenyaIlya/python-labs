import os
import time
import uuid
import logging
import dateparser
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from datetime import datetime, timedelta


class ParsedPostInfo:
    def __init__(self, post_url, username, user_karma, user_cake_day, post_karma, comment_karma,
                 comments_number, votes_number, post_category, post_date):
        self.post_url = post_url
        self.username = username
        self.user_karma = user_karma
        self.user_cake_day = user_cake_day
        self.post_karma = post_karma
        self.comment_karma = comment_karma
        self.comments_number = comments_number
        self.votes_number = votes_number
        self.post_category = post_category
        self.post_date = post_date

        self.unique_id = uuid.uuid1().hex

    def __str__(self):
        return f"{self.unique_id};{self.post_url};{self.username};{self.user_karma};" \
               f"{self.user_cake_day.date()};{self.comments_number};{self.votes_number};" \
               f"{self.post_category};{self.post_date.date()}"

    def write_to_file(self, file_path):
        with open(file_path, "a") as file:
            file.write(f"{self.__str__()}{os.linesep}")


def create_file():
    current_date = datetime.now()
    filename = f"reddit-{current_date.strftime('%Y%m%d%H%M')}.txt"
    file = open(filename, "a")
    file.close()

    return filename


def parse_reddit_page():
    filename = create_file()
    browser = webdriver.Chrome("/usr/lib/chromium-browser/chromedriver")
    browser.maximize_window()
    browser.get("https://www.reddit.com/top/?t=month")
    body_tag, total_posts_count = browser.find_element_by_tag_name("body"), 100

    for i in range(1):
        body_tag.send_keys(Keys.PAGE_DOWN)
        time.sleep(0.2)

    time.sleep(1)
    html = browser.page_source

    soup = BeautifulSoup(html, 'html.parser')
    all_posts_html = soup.select_one("html > body > div:nth-of-type(1) > div > div:nth-of-type(2) > div:nth-of-type(2)"
                                     "> div > div > div > div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(1)"
                                     "> div:nth-of-type(5)")
    single_posts = all_posts_html.find_all("div", class_="Post")

    for post in single_posts[:5]:
        votes_number = post.select_one("div > div > div").get_text()
        post_url = post.find("a", class_="_3jOxDPIQ0KaOWpzvSQo-1s")["href"]

        post_category_wrapper = post.find("div", class_="_3AStxql1mQsrZuUIFP9xSg nU4Je7n-eSXStTBAPMYt8")

        # Template: r/category_name
        post_category = post_category_wrapper.find("a", class_="_3ryJoIoycVkA88fy40qNJc").get_text()

        # Template: u/username
        name_parse_string = post.find("a", class_="_2tbHP6ZydRpjI44J3syuqC _23wugcdiaj44hdfugIAlnX"
                                                  " oQctV4n0yUb0uiHDdGnmE")

        # User deleted, but post exist
        try:
            username = name_parse_string.get_text()
            user_page_url = "".join(["https://www.reddit.com", name_parse_string["href"]])
        except AttributeError:
            continue

        publish_date = post.find("a", class_="_3jOxDPIQ0KaOWpzvSQo-1s").get_text()

        days_ago = int(publish_date.split(" ")[0])
        publish_date = datetime.today() - timedelta(days=days_ago)

        comments_number = post.select_one("div > div > div:nth-of-type(2)").find_all(recursive=False)[-1]
        comments_number = comments_number.select("a > span")

        # Representation may have distinct html formats
        if len(comments_number) == 1:
            comments_number = comments_number[0].get_text().split(" ")[0]
        else:
            comments_number = comments_number[0].select_one("div").find_all(recursive=False)[-1].get_text()

        # browser.find_element_by_tag_name("body").send_keys(Keys.COMMAND + 't')
        browser.execute_script(f"window.open('{user_page_url}');")
        browser.switch_to.window(browser.window_handles[1])
        # browser.get(user_page_url)
        time.sleep(2)

        # element_to_hover_over = browser.find_element_by_id("profile--id-card--highlight-tooltip--karma")
        # hover = webdriver.ActionChains(browser).move_to_element(element_to_hover_over)
        # hover.perform()
        # time.sleep(3)
        # # data_in_the_bubble = browser.find_element_by_xpath("//*[@id='profile--id-card--highlight-tooltip--karma']")
        # # hover_data = data_in_the_bubble.get_attribute("innerHTML")
        # print(browser)

        user_page_html = browser.page_source
        soup = BeautifulSoup(user_page_html, 'html.parser')
        user_profile_info_div_tag = soup.select_one("html > body > div:nth-of-type(1) > div > div:nth-of-type(2) >"
                                                    "div:nth-of-type(2) > div > div > div > div:nth-of-type(2) >"
                                                    "div:nth-of-type(4) > div:nth-of-type(2) > div >"
                                                    "div:nth-of-type(1) > div > div:nth-of-type(4)")

        browser.close()
        browser.switch_to.window(browser.window_handles[0])
        # Age average limitations
        try:
            user_karma = user_profile_info_div_tag.select_one("div > div > span").get_text()
            user_cake_day = dateparser.parse(user_profile_info_div_tag
                                             .select_one("div:nth-of-type(2) > div > span")
                                             .get_text())
        except AttributeError:
            continue
        else:
            ParsedPostInfo(post_url, username.lstrip("u/"), user_karma, user_cake_day, 0, 0, comments_number,
                           votes_number, post_category.lstrip("r/"), publish_date).write_to_file(filename)

    browser.quit()


if __name__ == "__main__":
    parse_reddit_page()
