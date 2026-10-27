"""What the OPP-115 data types and purposes mean, in the words policies use.

Written from the OPP-115 annotation scheme (Wilson et al., 2016). Reviewers get the entries for
the data types and purposes of their candidates; the finder adds the example words to its policy
searches so that the linked paragraphs include those that name the data in everyday terms.
"""
DATA_TYPES = {
    "Computer information": "device and browser information: browser type, operating system, device type or model, "
                            "screen resolution, hardware, internet service provider",
    "Contact": "contact details: name, email address, phone number, postal or mailing address",
    "Cookies and tracking elements": "cookies, web beacons, pixel tags, clear gifs, flash cookies, tracking technologies",
    "Demographic": "age, date of birth, gender, zip code, income, education, occupation",
    "Financial": "credit or debit card, payment and billing information, bank account, purchase or transaction history",
    "Health": "health, medical or fitness information, physical activity",
    "IP address and device IDs": "IP address, device identifier, advertising ID, UDID, IMEI, MAC address",
    "Location": "geolocation, GPS, precise or approximate location, location derived from the IP address",
    "Personal identifier": "government identifiers: social security number, passport, driver's licence, national ID",
    "Social media data": "information from social networks: social profile, friends, likes, posts",
    "Survey data": "answers to surveys, questionnaires, polls, contests or sweepstakes",
    "User online activities": "usage data: pages visited, clicks, browsing or search history, time spent, features used",
    "User profile": "account information: username, password, preferences, profile or account settings",
}
PURPOSES = {
    "Basic service/feature": "providing the service or feature the user asked for (account, orders, delivery, support)",
    "Additional service/feature": "optional extras (newsletters, contests, social or community features)",
    "Advertising": "showing ads, including targeted or interest-based advertising",
    "Marketing": "the company's own promotions, offers and marketing messages",
    "Analytics/Research": "measuring and understanding use of the service, statistics, research, improving the service",
    "Personalization/Customization": "tailoring content or recommendations to the user",
    "Service Operation and Security": "running and securing the service: security, fraud prevention, debugging, crash "
                                      "reports",
    "Legal requirement": "complying with the law or legal requests",
    "Merger/Acquisition": "transfers in a merger, acquisition or sale of the business",
}


def data_words(data_type: str) -> str:
    """Example words for a data type, for search queries ("" if unknown)."""
    desc = DATA_TYPES.get(data_type, "")
    return desc.split(":", 1)[-1].replace(",", " ")


def glossary(data_types, purposes) -> str:
    lines = [f"- {d}: {DATA_TYPES[d]}" for d in sorted(set(data_types)) if d in DATA_TYPES]
    lines += [f"- purpose \"{p}\": {PURPOSES[p]}" for p in sorted(set(purposes)) if p in PURPOSES]
    return "\n".join(lines)


# Words that show a sentence names the data type (lower case; matched at the start of a word,
# so "age" does not match "page" but does match "ages")
KEYWORDS = {
    "Computer information": ["browser", "operating system", "device type", "device model", "computer", "hardware",
                             "screen resolution", "internet service provider", "isp", "device information",
                             "mobile device"],
    "Contact": ["email", "e-mail", "phone", "telephone", "mailing address", "postal address", "address", "name",
                "contact"],
    "Cookies and tracking elements": ["cookie", "web beacon", "pixel", "clear gif", "tracking technolog", "tag"],
    "Demographic": ["age", "birth", "gender", "zip code", "postal code", "income", "education", "occupation",
                    "demographic"],
    "Financial": ["credit card", "debit card", "payment", "billing", "bank", "purchase", "transaction", "financial"],
    "Health": ["health", "medical", "fitness", "activity", "heart"],
    "IP address and device IDs": ["ip address", "device id", "device identifier", "advertising id", "udid", "imei",
                                  "mac address", "identifier"],
    "Location": ["location", "geolocation", "gps", "geographic", "latitude", "where you are"],
    "Personal identifier": ["social security", "passport", "driver", "national id", "government", "identification number",
                            "identifier"],
    "Social media data": ["social media", "social network", "facebook", "twitter", "friends", "profile picture"],
    "Survey data": ["survey", "questionnaire", "poll", "contest", "sweepstake"],
    "User online activities": ["pages", "clicks", "browsing", "search", "usage", "visit", "activity", "interaction"],
    "User profile": ["account", "username", "user name", "password", "preference", "profile"],
}


def mentions_data(text: str, data_type: str) -> bool:
    import re
    low = (text or "").lower()
    return any(re.search(r"\b" + re.escape(k), low) for k in KEYWORDS.get(data_type, [data_type.lower()]))
