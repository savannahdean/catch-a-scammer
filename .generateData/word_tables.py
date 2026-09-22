'''
domains
ip_addresses
hosting_providers
malware
campaigns
threat_actors
web_articles
'''

import random

random.seed(50)

def generate_domains():

    nouns = open("nounlist.txt", "r")
    adjectives = open("english-adjectives.txt", "r")

    for number in range(1000):

        randomNoun = random.randrange(1, 6801)
        randomAdj = random.randrange(1, 1803)

        domain = f"https://{random.choice(adjectives)}{random.choice(nouns)}.com"
        print(domain)

    nouns.close()
    
    return


generate_domains()