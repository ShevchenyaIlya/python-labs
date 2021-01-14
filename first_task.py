import os
import time
import uuid
import logging
import dateparser
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait
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
               f"{self.post_karma};{self.comment_karma};{self.post_date.date()};{self.comments_number};" \
               f"{self.votes_number};{self.post_category}"

    def write_to_file(self, file_path):
        with open(file_path, "a") as file:
            file.write(f"{self.__str__()}{os.linesep}")


def create_file():
    current_date = datetime.now()
    filename = f"reddit-{current_date.strftime('%Y%m%d%H%M')}.txt"
    file = open(filename, "a")
    file.truncate(0)
    file.close()

    return filename


def get_posts_list(html):
    soup = BeautifulSoup(html, "html.parser")
    all_posts_html = soup.select_one("html > body > div:nth-of-type(1) > div > div:nth-of-type(2) > div:nth-of-type(2)"
                                     "> div > div > div > div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(1)"
                                     "> div:nth-of-type(5)")

    return all_posts_html.find_all("div", class_="Post")


def parse_reddit_page():
    logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
    logger = logging.getLogger("reddit_parser")
    logger.setLevel(logging.DEBUG)

    filename = create_file()

    if os.path.exists(filename):
        logger.info(f"The file was created(name: {filename})!")
    else:
        logger.error("The file was not created!")

    options = webdriver.ChromeOptions()
    options.add_argument('headless')
    options.add_argument('window-size=1920x1080')

    browser = webdriver.Chrome("/usr/lib/chromium-browser/chromedriver", chrome_options=options)
    browser.get("https://www.reddit.com/top/?t=month")
    body_tag, total_posts_count, parsed_post_count = browser.find_element_by_tag_name("body"), 0, 0
    try:
        while parsed_post_count < 100:
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

            try:
                username = name_parse_string.get_text()
                user_page_url = "".join(["https://www.reddit.com", name_parse_string["href"]])
            except AttributeError:
                total_posts_count += 1
                logger.debug(f"The post (post_id: {post_id}, url: {post_url}) exists, but the user has been deleted!")
                continue

            publish_date = post.find("a", class_="_3jOxDPIQ0KaOWpzvSQo-1s").get_text()
            days_ago = int(publish_date.split(" ")[0])
            post_date = datetime.today() - timedelta(days=days_ago)

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
            soup = BeautifulSoup(user_page_html, "html.parser")
            user_profile_info_div_tag = soup.select_one("html > body > div:nth-of-type(1) > div > div:nth-of-type(2) >"
                                                        "div:nth-of-type(2) > div > div > div > div:nth-of-type(2) >"
                                                        "div:nth-of-type(4) > div:nth-of-type(2) > div >"
                                                        "div:nth-of-type(1) > div > div:nth-of-type(4)")

            browser.close()
            browser.switch_to.window(browser.window_handles[0])
            popup_menu = browser.find_element_by_id(f"UserInfoTooltip--{post_id}")
            popup_menu = popup_menu.find_element_by_xpath("..")
            hover = webdriver.ActionChains(browser).move_to_element(popup_menu)
            hover.perform()

            wait = WebDriverWait(browser, 20)
            element = wait.until(
                expected_conditions.element_to_be_clickable((By.ID, f"UserInfoTooltip--{post_id}-hover-id"))
            )

            popup_menu = BeautifulSoup(browser.page_source, "html.parser")\
                .find("div", id=f"UserInfoTooltip--{post_id}-hover-id")\
                .find_all("div", class_="_18aX_pAQub_mu1suz4-i8j")

            post_karma, comment_karma = popup_menu[0].get_text(), popup_menu[1].get_text()

            try:
                total_posts_count += 1
                user_karma = user_profile_info_div_tag.select_one("div > div > span").get_text()
                user_cake_day = dateparser.parse(user_profile_info_div_tag
                                                 .select_one("div:nth-of-type(2) > div > span")
                                                 .get_text())
            except AttributeError:
                logger.debug(f"Failed to access user(username: {username}, link: {user_page_url}) page due to age limit!")
                continue
            else:
                ParsedPostInfo(post_url, username.lstrip("u/"), user_karma, user_cake_day, post_karma,
                               comment_karma, comments_number, votes_number, post_category.lstrip("r/"),
                               post_date).write_to_file(filename)
                logger.debug(f"All information has been received on this post(url: {post_url})")
                parsed_post_count += 1
        else:
            logger.info("100 records were successfully placed in the file!")
    except Exception as error:
        print(error)
        browser.quit()


if __name__ == "__main__":
    parse_reddit_page()

