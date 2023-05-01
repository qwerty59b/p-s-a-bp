"""
This module defines a Telegram bot that can be used to bypass the try2link.com link shortener in
order to access direct download links for movies and TV shows available on the psa website. The bot
listens for messages containing psa links and sends a resolution selection message for each link.
When the user selects a resolution, the bot generates a message with the corresponding direct
download links and sends it as a reply to the user's message. The bot also handles authorization of
users and logging of events.

The module defines the following functions:
- autorization(user_id: int) -> None: checks if a given user is authorized to use the bot
- handle_message(app: Client, message: Message) -> None: handles incoming messages in private or
group chats
- handle_callback(app: Client, query: CallbackQuery) -> None: callback function that handles user
input
- try2link_bypass(url: str) -> requests.Response: bypasses the try2link.com link shortener for a
given url and returns the bypassed url
- try2link_scrape(url: str) -> requests.Response: scrapes the given URL using cloudscraper and
extracts the final URL after following any redirects, then bypasses try2link.com using the
extracted URL
- psa_bypasser(psa_url: str, selection: str) -> list[requests.Response]: sends a GET request to
`psa_url`, scrapes for links in the page, and returns a list of `requests.Response` objects that
match the `selection` parameter
"""
# Logger module
import logging
# Python dotenv modules
import os
from dotenv import load_dotenv
# Uvloop module
try:
	import uvloop
	use_uvloop: bool = True
except ModuleNotFoundError:
	use_uvloop: bool = False
import asyncio
# Pyrogram modules
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, UserNotParticipant
# PSA bypasser modules
import re
import time
import requests 
import cloudscraper 
from bs4 import BeautifulSoup, ResultSet


# Load system variables
load_dotenv()
# Initialize logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger: logging.Logger = logging.getLogger(os.getenv("SESSION_NAME"))


# Handling uvloop
if use_uvloop:
	uvloop.install()
	logger.info("Using uvloop. High performance loop activated.")
else:
	logger.warning("Not using uvloop. Low performance loop activated.")
del(use_uvloop)
# Initialize bot
SESSION_NAME: str = os.getenv("SESSION_NAME")
CHAT: str = os.getenv("CHAT")

app = Client("my_bot", session_string=SESSION_NAME)	
	
logger.info("Bot started!")


async def autorization(user_id: int) -> None:
	"""
	Checks if the given user is authorized to use the bot.
	:param user_id: The ID of the user to check.
	:type user_id: int
	:raises Exception: If the user is not a member of the chat.
	"""
	try:
		await app.get_chat_member(CHAT, user_id)
	except UserNotParticipant:
		raise Exception("You are not allowed to use this bot.")


@app.on_message(filters.private | filters.group)
async def handle_message(app: Client, message: Message) -> None:
	"""
	Handle incoming messages in private or group chats and send a resolution selection message
	:param app: Telegram Client
	:param message: Telegram Message
	:return: None
	"""
	await autorization(message.from_user.id)
	if not re.search("https://psa\.(pm|re)/", message.text.lower()):
		return
	try:
		# Extract links from the message
		links: list = [
			item
			for item in message.text.lower().replace("," and "\n", " ").split(" ")
			if re.search("https://psa\.(pm|re)/", message.text.lower())
		]
		# Send a resolution selection message for each link
		for link in links:
			match link.split("/")[3]:
				case "movie":
					await message.reply(
						f"**Choose a resolution for:**\n{link}",
						quote=True,
						reply_markup=InlineKeyboardMarkup(
							[
								[
									InlineKeyboardButton(
										"🔵 720P", callback_data=f"720p {link}"
									),
									InlineKeyboardButton(
										"🟠 1080P", callback_data=f"1080p {link}"
									),
									InlineKeyboardButton(
										"🔴 2160P", callback_data=f"2160p {link}"
									)
								],
								[
									InlineKeyboardButton(
										"❌ Cancel", callback_data="cancel"
									)
								]
							]
						)
					)
				case "tv-show":
					await message.reply(
						f"**Select an option or resolution for:**\n{link}",
						quote=True,
						reply_markup=InlineKeyboardMarkup(
							[
								[
									InlineKeyboardButton(
										"🔵 720P", callback_data=f"720p {link}"
									),
									InlineKeyboardButton(
										"🟠 1080P", callback_data=f"1080p {link}"
									),
									InlineKeyboardButton(
										"🔴 2160P", callback_data=f"2160p {link}"
									)
								],
								[
									InlineKeyboardButton(
										"🔵 Latest", callback_data=f"l720p {link}"
									),
									InlineKeyboardButton(
										"🟠 Latest", callback_data=f"l1080p {link}"
									),
									InlineKeyboardButton(
										"🔴 Latest", callback_data=f"l2160p {link}"
									)
								],
								[
									InlineKeyboardButton(
										"❌ Cancel", callback_data="cancel"
									)
								]
							]
						)
					)
	except FloodWait as wait:
		await asyncio.sleep(wait)
	except Exception as error:
		await message.reply(f"**⚠️ Error:** {error}", quote=True)


@app.on_callback_query()
async def handle_callback(app: Client, query: CallbackQuery) -> None:
	"""
	Callback function that handles user input.
	Args:
		app (telegram.client.Client): The Telegram client instance.
		query (telegram.CallbackQuery): The user's callback query.
	Returns:
		None.
	Raises:
		FloodWait: If the Telegram API has returned a flood wait error.
		Exception: If an unexpected error occurs.
	This function processes the user's callback query and sends a message with a list of torrent links.
	The function first checks whether the user is authorized, then processes the query data to get the URL and selection.
	It then calls the 'psa_bypasser' function to get a list of links, and generates a message string with the links.
	Finally, the function sends the message as a reply to the user's message.
	If an error occurs, the function logs the error and sends an error message to the user.
	"""
	await autorization(query.message.reply_to_message.from_user.id)
	try:
		await query.message.delete()
		if query.data == "cancel":
			await query.answer(text="❌ Cancelled", show_alert=False)
			return
		url: str = query.data.split(" ")[1]
		selection: str = query.data.split(" ")[0]
		links: list[requests.Response] = await psa_bypasser(url, selection)
		message: str = "**You can download torrent here:**\n"
		for counter, link in enumerate(links, start=1):
			name: str = " ".join(link.split("/")[3].split("-")).capitalize().strip()
			message += f"{counter}. [{name}]({link})\n"
		await query.message.reply_to_message.reply(text=message, quote=True)
	except FloodWait as wait:
		logger.warning(f"Flood wait: {wait}")
		await asyncio.sleep(wait)
	except Exception as error:
		logger.error(error)
		await query.message.reply_to_message.reply(f"**⚠️ Error:** {error}", quote=True)


# PSA bypass code base (https://github.com/xcscxr/psa)
async def try2link_bypass(url: str) -> requests.Response:
	"""
	Bypasses the try2link.com link shortener for the given url and returns the bypassed url.
	Parameters:
		url (str): The URL to be bypassed.
	Returns:
		requests.Response: The bypassed URL in a requests.Response object.
	Raises:
		N/A
	"""
    # function body
	client: cloudscraper.CloudScraper = cloudscraper.create_scraper(allow_brotli=False)
	url: str = url[:-1] if url[-1] == '/' else url
	params: tuple[tuple[str['d'], int]] = (('d', int(time.time()) + (60 * 4)),)
	r: requests.Response = client.get(
		url, params=params, headers= {'Referer': 'https://newforex.online/'}
	)
	soup: BeautifulSoup = BeautifulSoup(r.text, 'html.parser')
	inputs: ResultSet = soup.find(id="go-link").find_all(name="input")
	data: dict = {input.get('name'): input.get('value') for input in inputs}
	await asyncio.sleep(7)
	headers: dict[str: str] = {
		'Host': 'try2link.com',
		'X-Requested-With': 'XMLHttpRequest',
		'Origin': 'https://try2link.com',
		'Referer': url
	}
	bypassed_url: requests.Response = client.post('https://try2link.com/links/go', headers=headers,data=data)
	return bypassed_url.json()["url"]


async def try2link_scrape(url: str) -> requests.Response:
	"""
	Scrape the given URL using cloudscraper and extract the final URL after
	following any redirects. Then bypass try2link.com using the extracted URL.
	Args:
		url (str): The URL to scrape.
	Returns:
		requests.Response: The response after bypassing try2link.com.
	"""
	client: cloudscraper.CloudScraper = cloudscraper.create_scraper(allow_brotli=False)	
	h: dict[str: str] = {
	'upgrade-insecure-requests': '1',
	'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36',
	}
	res: requests.Response = client.get(url, cookies={}, headers=h)
	url: str = 'https://try2link.com/'+re.findall('try2link\.com\/(.*?) ', res.text)[0]
	bypass: requests.Response = await try2link_bypass(url)
	return bypass


async def psa_bypasser(psa_url: str, selection: str) -> list[requests.Response]:
	"""
	Sends a GET request to `psa_url`, scrapes for links in the page, and returns a list
	of `requests.Response` objects that match the `selection` parameter.
		:param psa_url: The URL to scrape for links.
		:type psa_url: str
		:param selection: The string to search for in the responses.
		:type selection: str
		:return: A list of `requests.Response` objects that match the `selection` parameter.
		:rtype: list[requests.Response]
		:raises Exception: If no results were found.
	"""
	items: list[requests.Response] = []
	client: cloudscraper.CloudScraper = cloudscraper.create_scraper(allow_brotli=False)
	r: requests.Response = client.get(psa_url)
	soup: ResultSet = BeautifulSoup(
		r.text, "html.parser"
	).find_all(
		class_="dropshadowboxes-drop-shadow dropshadowboxes-rounded-corners dropshadowboxes-inside-and-outside-shadow dropshadowboxes-lifted-both dropshadowboxes-effect-default"
	)
	for link in soup:
		try:
			exit_gate: str = link.a.get("href")
			result: requests.Response = await try2link_scrape(exit_gate)
			if selection[0] == "l" and selection[1:] in result:
				current: str = " ".join(result.split("/")[3].split("-")[:-1]).strip()
				if len(items) == 0 or (len(items) > 0 and current in result[len(items)-1]):
					items.append(result)
				else:
					break
			elif selection in result:
				items.append(result)
		except: pass
	if len(items) == 0:
		raise Exception("No results found!")
	return items


if __name__ == "__main__":
	try:
		app.run()
		logger.info("Bot stopped!")
	except KeyboardInterrupt:
		logger.error("Keyboard interrupt!")
