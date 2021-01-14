import os
import uuid
import logging
import argparse
import dateparser
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from datetime import datetime, timedelta
import traceback


def serialize_output_string(parsed_data):
    sequence = ["post_url", "username", "user_karma", "user_cake_day", "post_karma", "comment_karma",
                "post_date", "comments_number", "votes_number", "post_category"]

    output_string = str(uuid.uuid1().hex)
    for field in sequence:
        output_string = ";".join([output_string, parsed_data[field]])

    return output_string


def write_parsed_info_to_file(parsed_info, filename):
    with open(filename, "a") as file:
        file.write(f"{parsed_info}{os.linesep}")


def config_browser(chrome_drive_path):
    options = webdriver.ChromeOptions()
    options.add_argument('headless')
    options.add_argument('window-size=1920x1080')
    return webdriver.Chrome(chrome_drive_path, chrome_options=options)


def generate_filename():
    current_date = datetime.now()
    return f"reddit-{current_date.strftime('%Y%m%d%H%M')}.txt"


def truncate_file_content(filename):
    # Truncate content of file
    if os.path.isfile(filename):
        with open(filename, "w") as file:
            file.truncate()


def get_posts_list(html):
    soup = BeautifulSoup(html, "html.parser")
    all_posts_html = soup.select_one("html > body > div:nth-of-type(1) > div > div:nth-of-type(2) > div:nth-of-type(2)"
                                     "> div > div > div > div:nth-of-type(2) > div:nth-of-type(3) > div:nth-of-type(1)"
                                     "> div:nth-of-type(5)")

    return all_posts_html.find_all("div", class_="Post")


def config_logger(log_level):
    logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
    logger = logging.getLogger("reddit_parser")
    logger.setLevel(log_level)
    return logger


def get_user_html_from_new_browser_tab(browser, user_page_url):
    browser.execute_script(f"window.open('{user_page_url}');")
    browser.switch_to.window(browser.window_handles[1])
    user_page_html = browser.page_source
    soup = BeautifulSoup(user_page_html, "html.parser")
    user_profile_info = soup.select_one("html > body > div:nth-of-type(1) > div > div:nth-of-type(2) >"
                                        "div:nth-of-type(2) > div > div > div > div:nth-of-type(2) >"
                                        "div:nth-of-type(4) > div:nth-of-type(2) > div >"
                                        "div:nth-of-type(1) > div > div:nth-of-type(4)")

    browser.close()
    browser.switch_to.window(browser.window_handles[0])
    return user_profile_info


def parse_reddit_page(chrome_drive_path, log_level, post_count):
    logger = config_logger(log_level)
    filename = generate_filename()
    truncate_file_content(filename)
    logger.info(f"The filename: {filename}!")
    browser = config_browser(chrome_drive_path)

    try:
        browser.get("https://www.reddit.com/top/?t=month")
        total_posts_count, parsed_post_count = 0, 0

        while parsed_post_count < post_count:
            parsed_data = {}
            single_posts = get_posts_list(browser.page_source)
            post = single_posts[total_posts_count]
            post_id = post["id"]
            current_post = browser.find_element_by_id(post_id)

            hover = webdriver.ActionChains(browser).move_to_element(current_post)
            hover.perform()

            parsed_data["votes_number"] = post.select_one("div > div > div").get_text()
            parsed_data["post_url"] = post.find("a", class_="_3jOxDPIQ0KaOWpzvSQo-1s")["href"]
            post_category_wrapper = post.find("div", class_="_3AStxql1mQsrZuUIFP9xSg nU4Je7n-eSXStTBAPMYt8")

            parsed_data["post_category"] = post_category_wrapper.find("a", class_="_3ryJoIoycVkA88fy40qNJc")\
                .get_text().lstrip("r/")
            name_parse_string = post.find("a", class_="_2tbHP6ZydRpjI44J3syuqC _23wugcdiaj44hdfugIAlnX"
                                                      " oQctV4n0yUb0uiHDdGnmE")

            try:
                parsed_data["username"] = name_parse_string.get_text().lstrip("u/")
                user_page_url = "".join(["https://www.reddit.com", name_parse_string["href"]])
            except AttributeError:
                total_posts_count += 1
                logger.debug(f"The post (post_id: {post_id}, url: {parsed_data['post_url']}) "
                             f"exists, but the user has been deleted!")
                continue

            publish_date = post.find("a", class_="_3jOxDPIQ0KaOWpzvSQo-1s").get_text()
            days_ago = int(publish_date.split(" ")[0])
            post_date = datetime.today() - timedelta(days=days_ago)
            parsed_data["post_date"] = str(post_date.date())

            comments_number = post.select_one("div > div > div:nth-of-type(2)").find_all(recursive=False)[-1]
            comments_number = comments_number.select("a > span")

            # Representation may have distinct html formats
            if len(comments_number) == 1:
                parsed_data["comments_number"] = comments_number[0].get_text().split(" ")[0]
            else:
                parsed_data["comments_number"] = comments_number[0].select_one("div").find_all(recursive=False)[-1]\
                    .get_text()

            user_profile_info = get_user_html_from_new_browser_tab(browser, user_page_url)
            popup_menu = browser.find_element_by_id(f"UserInfoTooltip--{post_id}")
            popup_menu = popup_menu.find_element_by_xpath("..")
            hover = webdriver.ActionChains(browser).move_to_element(popup_menu)
            hover.perform()

            WebDriverWait(browser, 10).until(
                expected_conditions.presence_of_element_located((By.ID, f"UserInfoTooltip--{post_id}-hover-id"))
            )

            popup_menu = BeautifulSoup(browser.page_source, "html.parser")\
                .find("div", id=f"UserInfoTooltip--{post_id}-hover-id")\
                .find_all("div", class_="_18aX_pAQub_mu1suz4-i8j")

            parsed_data["post_karma"], parsed_data["comment_karma"] = popup_menu[0].get_text(), popup_menu[1].get_text()

            try:
                total_posts_count += 1
                parsed_data["user_karma"] = user_profile_info.select_one("div > div > span").get_text()
                user_cake_day = dateparser.parse(user_profile_info
                                                 .select_one("div:nth-of-type(2) > div > span")
                                                 .get_text())
                parsed_data["user_cake_day"] = str(user_cake_day.date())
            except AttributeError:
                logger.debug(f"Failed to access user(username: {parsed_data['username']}, "
                             f"link: {user_page_url}) page due to age limit!")
                continue
            else:
                parsed_info = serialize_output_string(parsed_data)
                write_parsed_info_to_file(parsed_info, filename)
                logger.debug(f"All information has been received on this post(url: {parsed_data['post_url']})")
                parsed_post_count += 1
        else:
            logger.info(f"{post_count} records were successfully placed in the file!")

    except Exception as exception:
        logger.error(exception)
        traceback.print_exc(chain=True)
        browser.quit()


def parse_command_line_arguments():
    argument_parser = argparse.ArgumentParser(description="Reddit parser")
    argument_parser.add_argument("--path", metavar="path", type=str, help="Chromedriver path",
                                 default="/usr/lib/chromium-browser/chromedriver")
    argument_parser.add_argument("--log_level", metavar="log_level", type=str, default="DEBUG",
                                 choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                                 help="Minimal logging level('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')")
    argument_parser.add_argument("--post_count", metavar="post_count", type=int, default=20,
                                 choices=range(0, 101), help="Parsed post count")
    args = argument_parser.parse_args()

    return args.path, args.log_level, args.post_count


def string_to_logging_level(log_level):
    possible_levels = {'DEBUG': logging.DEBUG, 'INFO': logging.INFO, 'WARNING': logging.WARNING,
                       'ERROR': logging.ERROR, 'CRITICAL': logging.CRITICAL}

    return possible_levels[log_level]


if __name__ == "__main__":
    chrome_driver, min_log_level, max_post_count = parse_command_line_arguments()
    if os.path.isfile(chrome_driver):
        parse_reddit_page(chrome_driver, string_to_logging_level(min_log_level), max_post_count)
