


from steam_web_api import Steam

steam = Steam()



res = steam.apps.get_app_details(1466060, country="RU", filters="price_overview")

print(res)

    # через 200 запросов начинает давать None. Сбрасывается каждые 5 минxx