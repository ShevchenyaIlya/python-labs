import os
import uuid
import logging
import argparse
import dateparser
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException


def write_to_file(filename, data):
    with open(filename, "w") as file:
        for serialize_post in data:
            file.write(f"{serialize_post}{os.linesep}")


def serialize_output_string(parsed_data):
    sequence = ["post_url", "username", "user_karma", "user_cake_day", "post_karma", "comment_karma",
                "post_date", "comments_number", "votes_number", "post_category"]

    output_string = str(uuid.uuid1().hex)
    for field in sequence:
        output_string = ";".join([output_string, parsed_data[field]])

    return output_string


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


def parse_publication_date(tag_with_date):
    publish_date = tag_with_date.get_text()
    days_ago = int(publish_date.split(" ")[0])
    post_date = datetime.today() - timedelta(days=days_ago)
    return str(post_date.date())


def parse_comment_number(post):
    comments_number = post.select_one("div > div > div:nth-of-type(2)").find_all(recursive=False)[-1]
    comments_number = comments_number.select("a > span")

    # Representation may have distinct html formats
    if len(comments_number) == 1:
        return comments_number[0].get_text().split(" ")[0]
    else:
        return comments_number[0].select_one("div").find_all(recursive=False)[-1].get_text()


def hover_current_post_element(browser, element):
    hover = webdriver.ActionChains(browser).move_to_element(element)
    hover.perform()


def parse_main_page(current_post_info, post, post_id, logger):
    current_post_info["votes_number"] = post.select_one("div > div > div").get_text()
    top_post_html_source = post.select_one("div:nth-of-type(2)").findChildren(recursive=False)[0]
    if top_post_html_source.name == "article":
        top_post_html_source = top_post_html_source.select_one("div > div > div:nth-of-type(2) > div")
    else:
        top_post_html_source = top_post_html_source.select_one("div > div:nth-of-type(2) > div")

    all_a_tags_inside_block = top_post_html_source.find_all("a")
    current_post_info["post_url"] = all_a_tags_inside_block[-1]["href"]
    current_post_info["post_category"] = top_post_html_source.select_one("div > a").get_text().lstrip("r/")

    # User deleted
    if len(all_a_tags_inside_block) == 2:
        logger.debug(f"The post (post_id: {post_id}, url: {current_post_info['post_url']}) "
                     f"exists, but the user has been deleted!")
        return None

    name_parse_string = all_a_tags_inside_block[1]
    current_post_info["username"] = name_parse_string.get_text().lstrip("u/")
    current_post_info["post_date"] = parse_publication_date(all_a_tags_inside_block[-1])
    current_post_info["comments_number"] = parse_comment_number(post)
    user_page_url = "".join(["https://www.reddit.com", name_parse_string["href"]])

    return user_page_url


def parse_user_page(browser, user_page_url, current_post_info, logger):
    user_profile_info = get_user_html_from_new_browser_tab(browser, user_page_url)

    try:
        current_post_info["user_karma"] = user_profile_info.select_one("div > div > span").get_text()
        user_cake_day = dateparser.parse(user_profile_info
                                         .select_one("div:nth-of-type(2) > div > span")
                                         .get_text())

        current_post_info["user_cake_day"] = str(user_cake_day.date())
    except AttributeError:
        logger.debug(f"Failed to access user(username: {current_post_info['username']}, "
                     f"link: {user_page_url}) page due to age limit!")
        return False

    return True


def parse_popup_menu(browser, post_id, current_post_info, logger):
    popup_menu = browser.find_element_by_id(f"UserInfoTooltip--{post_id}")
    popup_menu = popup_menu.find_element_by_xpath("..")
    hover_current_post_element(browser, popup_menu)

    try:
        popup_element = WebDriverWait(browser, 10).until(
            expected_conditions.presence_of_element_located((By.ID, f"UserInfoTooltip--{post_id}-hover-id"))
        )
    except (TimeoutException, StaleElementReferenceException):
        logger.debug(f"Popup menu does not appear for this post(url: {current_post_info['post_url']}).")
        return False

    popup_menu_info = BeautifulSoup(popup_element.get_attribute("innerHTML"), "html.parser")\
        .findChildren(recursive=False)[-2]\
        .findChildren(recursive=False)[-3]

    tags_with_numbers = list(popup_menu_info.children)
    current_post_info["post_karma"] = tags_with_numbers[1].select_one("div").get_text()
    current_post_info["comment_karma"] = tags_with_numbers[2].select_one("div").get_text()

    return True


def parse_reddit_page(chrome_drive_path, post_count, logger):
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
            single_posts = get_posts_list(browser.page_source)
            post = single_posts[total_posts_count]
            post_id = post["id"]

            current_post = browser.find_element_by_id(post_id)
            hover_current_post_element(browser, current_post)

            user_page_url = parse_main_page(current_post_info, post, post_id, logger)
            if user_page_url is None:
                total_posts_count += 1
                continue

            if not parse_popup_menu(browser, post_id, current_post_info, logger):
                total_posts_count += 1
                continue

            total_posts_count += 1
            if parse_user_page(browser, user_page_url, current_post_info, logger):
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


def parse_command_line_arguments():
    argument_parser = argparse.ArgumentParser(description="Reddit parser")
    argument_parser.add_argument("--path", metavar="path", type=str, help="Chromedriver path",
                                 default="/usr/lib/chromium-browser/chromedriver")
    argument_parser.add_argument("--log_level", metavar="log_level", type=str, default="DEBUG",
                                 choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                                 help="Minimal logging level('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')")
    argument_parser.add_argument("--post_count", metavar="post_count", type=int, default=100,
                                 choices=range(0, 101), help="Parsed post count")
    args = argument_parser.parse_args()

    return args.path, args.log_level, args.post_count


def string_to_logging_level(log_level):
    possible_levels = {'DEBUG': logging.DEBUG, 'INFO': logging.INFO, 'WARNING': logging.WARNING,
                       'ERROR': logging.ERROR, 'CRITICAL': logging.CRITICAL}

    return possible_levels[log_level]


if __name__ == "__main__":
    chrome_driver, min_log_level, max_post_count = parse_command_line_arguments()
    configured_logger = config_logger(string_to_logging_level(min_log_level))

    if os.path.isfile(chrome_driver):
        parse_reddit_page(chrome_driver, max_post_count, configured_logger)
    else:
        configured_logger.error(f"Chrome drive does not exists at this link: {chrome_driver}!")
