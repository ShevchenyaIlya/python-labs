import os
import uuid
import time
import json
import logging
import argparse
import dateparser
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException


def write_to_file(filename: str, data: List[str]) -> None:
    with open(filename, "w") as file:
        for serialize_post in data:
            file.write(f"{serialize_post}{os.linesep}")


def serialize_output_string(parsed_data: Dict[str, str]) -> str:
    sequence = ["post_url", "username", "user_karma", "user_cake_day", "post_karma", "comment_karma",
                "post_date", "comments_number", "votes_number", "post_category"]

    output_string = str(uuid.uuid1().hex)
    for field in sequence:
        output_string = ";".join([output_string, parsed_data[field]])

    return output_string


def config_browser(chrome_drive_path: str) -> webdriver.Chrome:
    caps = DesiredCapabilities().CHROME
    caps["pageLoadStrategy"] = "normal"  # possible: "normal", "eagle", "none"
    options = webdriver.ChromeOptions()
    options.add_argument('headless')
    options.add_argument('window-size=1920x1080')
    options.add_argument('--blink-settings=imagesEnabled=false')
    options.add_argument('--no-proxy-server')

    return webdriver.Chrome(chrome_drive_path, chrome_options=options, desired_capabilities=caps)


def generate_filename() -> str:
    current_date = datetime.now()
    return f"reddit-{current_date.strftime('%Y%m%d%H%M')}.txt"


def truncate_file_content(filename: str) -> None:
    """Truncate content of file if file exist"""
    if os.path.isfile(filename):
        with open(filename, "w") as file:
            file.truncate()


def get_posts_list(html, xpath_templates):
    soup = BeautifulSoup(html, "lxml")
    all_posts_html = soup.select_one(xpath_templates["all_posts_block"])

    return all_posts_html.find_all("div", class_="Post")


def config_logger(log_level: int) -> logging.Logger:
    logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
    logger = logging.getLogger("reddit_parser")
    logger.setLevel(log_level)
    return logger


def get_user_html_from_new_browser_tab(browser, user_page_url, xpath_templates):
    browser.execute_script(f"window.open('{user_page_url}');")
    browser.switch_to.window(browser.window_handles[1])
    user_page_html = browser.page_source
    soup = BeautifulSoup(user_page_html, "lxml")
    user_profile_info = soup.select_one(xpath_templates["user_profile_block"])

    browser.close()
    browser.switch_to.window(browser.window_handles[0])
    return user_profile_info


def parse_publication_date(tag_with_date):
    publish_date = tag_with_date.get_text()
    days_ago = int(publish_date.split(" ")[0])
    post_date = datetime.today() - timedelta(days=days_ago)
    return str(post_date.date())


def parse_comment_number(post, xpath_templates):
    comments_number = post.select_one(xpath_templates["comments_number_inside_post"]).find_all(recursive=False)[-1]
    comments_number = comments_number.select("a > span")

    # Representation may have distinct html formats
    if len(comments_number) == 1:
        return comments_number[0].get_text().split(" ")[0]
    else:
        return comments_number[0].select_one("div").find_all(recursive=False)[-1].get_text()


def hover_current_post_element(browser, element):
    hover = webdriver.ActionChains(browser).move_to_element(element)
    hover.perform()


def parse_main_page(current_post_info, post, post_id, logger, xpath_templates):
    current_post_info["votes_number"] = post.select_one(xpath_templates["votes_number_inside_post"]).get_text()

    top_post_html_source = post.select_one(xpath_templates["top_post_line_block"]).findChildren(recursive=False)[0]
    if top_post_html_source.name == "article":
        top_post_html_source = top_post_html_source.select_one(xpath_templates["article_shell"])
    else:
        top_post_html_source = top_post_html_source.select_one(xpath_templates["div_shell"])

    all_a_tags_inside_block = top_post_html_source.find_all("a")
    current_post_info["post_url"] = all_a_tags_inside_block[-1]["href"]
    current_post_info["post_category"] = top_post_html_source.select_one(xpath_templates["post_category"])\
        .get_text().lstrip("r/")

    # User deleted
    if len(all_a_tags_inside_block) == 2:
        logger.debug(f"The post (post_id: {post_id}, url: {current_post_info['post_url']}) "
                     f"exists, but the user has been deleted!")
        return None

    name_parse_string = all_a_tags_inside_block[1]
    current_post_info["username"] = name_parse_string.get_text().lstrip("u/")
    current_post_info["post_date"] = parse_publication_date(all_a_tags_inside_block[-1])
    current_post_info["comments_number"] = parse_comment_number(post, xpath_templates)
    user_page_url = "".join(["https://www.reddit.com", name_parse_string["href"]])

    return user_page_url


def parse_user_page(user_profile_info, user_page_url, current_post_info, logger, xpath_templates):
    try:
        current_post_info["user_karma"] = user_profile_info.select_one(xpath_templates["user_karma"]).get_text()
        user_cake_day = dateparser.parse(user_profile_info
                                         .select_one(xpath_templates["user_cake_day"])
                                         .get_text())

        current_post_info["user_cake_day"] = str(user_cake_day.date())
    except AttributeError:
        logger.debug(f"Failed to access user(username: {current_post_info['username']}, "
                     f"link: {user_page_url}) page due to age limit!")
        return False

    return True


def navigate_popup_menu(browser, post_id, current_post_info, logger):
    popup_menu = browser.find_element_by_id(f"UserInfoTooltip--{post_id}")
    popup_menu = popup_menu.find_element_by_xpath("..")
    hover_current_post_element(browser, popup_menu)

    try:
        popup_element = WebDriverWait(browser, 5).until(
            expected_conditions.presence_of_element_located((By.ID, f"UserInfoTooltip--{post_id}-hover-id"))
        )
    except (TimeoutException, StaleElementReferenceException):
        logger.debug(f"Popup menu does not appear for this post(url: {current_post_info['post_url']}).")
        return None

    return popup_element


def parse_popup_menu(current_post_info, popup_element):
    popup_menu_info = BeautifulSoup(popup_element.get_attribute("innerHTML"), "html.parser")\
        .findChildren(recursive=False)[-2]\
        .findChildren(recursive=False)[-3]

    tags_with_numbers = list(popup_menu_info.children)
    current_post_info["post_karma"] = tags_with_numbers[1].select_one("div").get_text()
    current_post_info["comment_karma"] = tags_with_numbers[2].select_one("div").get_text()


def parse_reddit_page(chrome_drive_path: str, post_count: int, logger: logging.Logger,
                      xpath_templates: Dict[str, str]) -> None:
    filename = generate_filename()
    truncate_file_content(filename)
    logger.info(f"The filename: {filename}!")
    browser = config_browser(chrome_drive_path)
    parsed_information = []

    try:
        browser.get("https://www.reddit.com/top/?t=month")
        total_posts_count, parsed_post_count = 0, 0

        while parsed_post_count < post_count:
            current_post_info = {}
            single_posts = get_posts_list(browser.page_source, xpath_templates)
            post = single_posts[total_posts_count]
            post_id = post["id"]

            current_post = browser.find_element_by_id(post_id)
            hover_current_post_element(browser, current_post)

            user_page_url = parse_main_page(current_post_info, post, post_id, logger, xpath_templates)
            if user_page_url is None:
                total_posts_count += 1
                continue

            popup_element = navigate_popup_menu(browser, post_id, current_post_info, logger)
            if popup_element is None:
                total_posts_count += 1
                continue

            parse_popup_menu(current_post_info, popup_element)

            total_posts_count += 1
            user_profile_info = get_user_html_from_new_browser_tab(browser, user_page_url, xpath_templates)
            if parse_user_page(user_profile_info, user_page_url, current_post_info, logger, xpath_templates):
                parsed_information.append(serialize_output_string(current_post_info))
                logger.debug(f"All information has been received on this post(url: {current_post_info['post_url']})")
                parsed_post_count += 1
            else:
                continue
        else:
            logger.info(f"{post_count} records were successfully placed in the file!")

    except Exception as exception:
        logger.error(exception, exc_info=True)
    finally:
        write_to_file(filename, parsed_information)
        browser.quit()


def parse_command_line_arguments() -> Tuple[str, str, int]:
    argument_parser = argparse.ArgumentParser(description="Reddit parser")
    argument_parser.add_argument("--path", metavar="path", type=str, help="Chromedriver path",
                                 default=find_chrome_driver())
    argument_parser.add_argument("--log_level", metavar="log_level", type=str, default="DEBUG",
                                 choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                                 help="Minimal logging level('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')")
    argument_parser.add_argument("--post_count", metavar="post_count", type=int, default=20,
                                 choices=range(0, 101), help="Parsed post count")
    args = argument_parser.parse_args()

    return args.path, args.log_level, args.post_count


def string_to_logging_level(log_level: str) -> int:
    possible_levels = {'DEBUG': logging.DEBUG, 'INFO': logging.INFO, 'WARNING': logging.WARNING,
                       'ERROR': logging.ERROR, 'CRITICAL': logging.CRITICAL}

    return possible_levels[log_level]


def find_chrome_driver() -> str:
    stream = os.popen('which -a chromedriver')
    return stream.read().rstrip(os.linesep)


def load_xpath_templates_from_json():
    with open('xpath_config.json') as json_file:
        xpath_templates = json.load(json_file)

    return xpath_templates


if __name__ == "__main__":
    chrome_driver, min_log_level, max_post_count = parse_command_line_arguments()
    configured_logger = config_logger(string_to_logging_level(min_log_level))
    xpath = load_xpath_templates_from_json()

    if os.path.isfile(chrome_driver):
        start = time.time()
        parse_reddit_page(chrome_driver, max_post_count, configured_logger, xpath)
        print(time.time() - start, " seconds.")
    else:
        configured_logger.error(f"Chrome drive does not exists at this link: {chrome_driver}!")
