import requests
import os

items = {
    "carrots.jpg": "carrots",
    "spinach.jpg": "spinach leaves",
    "hen_eggs.jpg": "eggs carton",
    "whole_milk.jpg": "whole milk glass",
    "cheddar.jpg": "cheddar cheese",
    "yoghurt.jpg": "plain yogurt bowl",
    "sourdough.jpg": "sourdough bread",
    "strawberry_jam.jpg": "strawberry jam",
    "raspberry_jam.jpg": "raspberry jam",
    "lemon_curd.jpg": "lemon curd",
    "apple_chutney.jpg": "apple chutney",
    "asparagus.jpg": "asparagus",
    "fresh_herbs.jpg": "fresh herbs",
    "whole_chicken.jpg": "raw whole chicken",
    "sausages.jpg": "raw sausages",
    "beef_mince.jpg": "beef mince",
    "strawberries.jpg": "strawberries",
    "raspberries.jpg": "raspberries",
    "apples.jpg": "apples",
    "pears.jpg": "pears",
    "apple_juice.jpg": "apple juice",
    "elderflower_cordial.jpg": "elderflower cordial",
    "lemonade.jpg": "lemonade"
}

os.makedirs("images", exist_ok=True)

for filename, query in items.items():
    url = f"https://source.unsplash.com/512x512/?{query}"
    response = requests.get(url)
    if response.status_code == 200:
        with open(os.path.join("images", filename), "wb") as f:
            f.write(response.content)
        print(f"Downloaded {filename}")
    else:
        print(f"Failed: {filename}")
