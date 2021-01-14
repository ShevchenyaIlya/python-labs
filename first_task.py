import os
import time
import uuid
import logging
import dateparser
from bs4 import BeautifulSoup
from selenium import webdriver
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
        return f"{self.unique_id};{self.post_url};{self.username};{self.user_karma};{self.user_cake_day.date()};" \
               f"{self.post_karma};{self.comment_karma};{self.comments_number};{self.votes_number};" \
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


def get_posts_list(html):
    soup = BeautifulSoup(html, 'html.parser')
    all_posts_html = soup.select_one("html > body > div:nth-of-type(1) > div > div:nth-of-type(2) > div:nth-of-type(2)"
                                     "> div > div > div > div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(1)"
                                     "> div:nth-of-type(5)")

    return all_posts_html.find_all("div", class_="Post")


def parse_reddit_page():
    filename = create_file()
    browser = webdriver.Chrome("/usr/lib/chromium-browser/chromedriver")
    browser.set_window_position(-2000, 0)
    browser.maximize_window()
    browser.get("https://www.reddit.com/top/?t=month")
    body_tag, total_posts_count, parsed_post_count = browser.find_element_by_tag_name("body"), 0, 0

    while parsed_post_count < 20:
        html = browser.page_source
        single_posts = get_posts_list(html)
        post = single_posts[total_posts_count]
        post_id = post["id"]
        current_post = browser.find_element_by_id(post_id)
        hover = webdriver.ActionChains(browser).move_to_element(current_post)
        hover.perform()

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
            total_posts_count += 1
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

        browser.execute_script(f"window.open('{user_page_url}');")
        browser.switch_to.window(browser.window_handles[1])

        user_page_html = browser.page_source
        soup = BeautifulSoup(user_page_html, 'html.parser')
        user_profile_info_div_tag = soup.select_one("html > body > div:nth-of-type(1) > div > div:nth-of-type(2) >"
                                                    "div:nth-of-type(2) > div > div > div > div:nth-of-type(2) >"
                                                    "div:nth-of-type(4) > div:nth-of-type(2) > div >"
                                                    "div:nth-of-type(1) > div > div:nth-of-type(4)")

        browser.close()
        browser.switch_to.window(browser.window_handles[0])
        input_el = browser.find_element_by_id(f'UserInfoTooltip--{post_id}')
        td_p_input = input_el.find_element_by_xpath('..')
        hover = webdriver.ActionChains(browser).move_to_element(td_p_input)
        hover.perform()
        time.sleep(2)

        popup_menu = BeautifulSoup(browser.page_source, 'html.parser')\
            .find("div", id=f"UserInfoTooltip--{post_id}-hover-id")
        popup_menu = popup_menu.find_all("div", class_="_18aX_pAQub_mu1suz4-i8j")
        post_karma, comment_karma = popup_menu[0].get_text(), popup_menu[1].get_text()

        # Age average limitations
        try:
            total_posts_count += 1
            user_karma = user_profile_info_div_tag.select_one("div > div > span").get_text()
            user_cake_day = dateparser.parse(user_profile_info_div_tag
                                             .select_one("div:nth-of-type(2) > div > span")
                                             .get_text())
        except AttributeError:
            continue
        else:
            ParsedPostInfo(post_url, username.lstrip("u/"), user_karma, user_cake_day, post_karma,
                           comment_karma, comments_number, votes_number, post_category.lstrip("r/"),
                           publish_date).write_to_file(filename)
            parsed_post_count += 1

    browser.quit()


if __name__ == "__main__":
    start = time.time()
    parse_reddit_page()
    print('It took', time.time() - start, 'seconds.')
