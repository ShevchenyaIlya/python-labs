import time
import dateparser
import uuid
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from datetime import datetime, timedelta


class ParsedInfo:
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
        return f"{self.unique_id} : {self.post_url} : {self.username} : {self.user_karma} : " \
               f"{self.user_cake_day.date()} : {self.comments_number} : {self.votes_number} : " \
               f"{self.post_category} : {self.post_date.date()}"

    def write_to_file(self, file_path):
        pass


def get_reddit_page():
    options = Options()
    options.add_argument("--lang=de-DE")
    browser = webdriver.Chrome("/usr/lib/chromium-browser/chromedriver", options=options)
    browser.maximize_window()
    browser.get("https://www.reddit.com/top/?t=month")
    body_tag = browser.find_element_by_tag_name("body")

    for i in range(1):
        body_tag.send_keys(Keys.PAGE_DOWN)
        time.sleep(0.3)

    time.sleep(1)
    html = browser.page_source

    soup = BeautifulSoup(html, 'html.parser')
    all_posts_html = soup.select_one("html > body > div:nth-of-type(1) > div > div:nth-of-type(2) > div:nth-of-type(2)"
                                     "> div > div > div > div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(1)"
                                     "> div:nth-of-type(5)")
    single_posts = all_posts_html.find_all("div", class_="Post")

    print(len(single_posts))
    parsed_post = []
    for post in single_posts[:5]:
        votes_number = post.select_one("div > div > div").get_text()
        post_url = "".join(["https://www.reddit.com", post.find("a", class_="_3jOxDPIQ0KaOWpzvSQo-1s")["href"]])

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

        day_before = int(publish_date.split(" ")[0])
        publish_date = datetime.today() - timedelta(days=day_before)

        comments_number = post.select_one("div > div > div:nth-of-type(2)").find_all(recursive=False)[-1]
        comments_number = comments_number.select("a > span")

        # Representation may have distinct html formats
        if len(comments_number) == 1:
            comments_number = comments_number[0].get_text().split(" ")[0]
        else:
            comments_number = comments_number[0].select_one("div").find_all(recursive=False)[-1].get_text()

        browser.get(user_page_url)
        time.sleep(3)

        # element_to_hover_over = browser.find_element_by_id("profile--id-card--highlight-tooltip--karma")
        # hover = webdriver.ActionChains(browser).move_to_element(element_to_hover_over)
        # hover.perform()
        # time.sleep(3)
        # data_in_the_bubble = browser.find_element_by_xpath("//*[@id='profile--id-card--highlight-tooltip--karma']")
        # hover_data = data_in_the_bubble.get_attribute("innerHTML")
        # print(hover_data)

        user_page_html = browser.page_source
        soup = BeautifulSoup(user_page_html, 'html.parser')
        user_profile_info_div_tag = soup.select_one("html > body > div:nth-of-type(1) > div > div:nth-of-type(2) >"
                                                    " div:nth-of-type(2) > div > div > div > div:nth-of-type(2) >"
                                                    " div:nth-of-type(4) > div:nth-of-type(2) > div > div:nth-of-type(1) >"
                                                    " div > div:nth-of-type(4)")

        # Age average limitations
        try:
            user_karma = user_profile_info_div_tag.select_one("div > div > span").get_text()
            user_cake_day = dateparser.parse(user_profile_info_div_tag
                                             .select_one("div:nth-of-type(2) > div > span")
                                             .get_text())
            parsed_post.append(ParsedInfo(post_url, username.lstrip("u/"), user_karma, user_cake_day, 0, 0,
                                          comments_number, votes_number, post_category.lstrip("r/"), publish_date))
        except AttributeError:
            continue

    browser.close()
    print()
    print(len(parsed_post))
    print()
    for post in parsed_post:
        print(post)


if __name__ == "__main__":
    get_reddit_page()
