import Tkinter as tk
import tkFileDialog
from py2neo import Graph
import string
import io
import pymsgbox
from PIL import Image

from google.cloud import vision
from google.cloud.vision import types

graph = Graph("http://neo4j:neo4j@localhost:7474/db/data/")

root = tk.Tk()
root.withdraw()

URL = tkFileDialog.askopenfilename()

def show_result(url1, url2):
    images = map(Image.open,[url1, url2])
    widths, heights = zip(*(i.size for i in images))

    total_width = sum(widths)
    max_height = max(heights)

    new_im = Image.new('RGB', (total_width, max_height))

    x_offset = 0
    for im in images:
        new_im.paste(im, (x_offset, 0))
        x_offset += im.size[0]+20

    new_im.show()

def fix_url(input):
    str = string.replace(input, '/', "\\")
    return str

def annotate(path):
    """Returns web annotations given the path to an image."""
    client = vision.ImageAnnotatorClient()

    if path.startswith('http') or path.startswith('gs:'):
        image = types.Image()
        image.source.image_uri = path

    else:
        with io.open(path, 'rb') as image_file:
            content = image_file.read()

        image = types.Image(content=content)

    web_detection = client.web_detection(image=image).web_detection

    return web_detection


def report(annotations):
    cypher = graph.cypher
    #this vairable stop loop after input "yes" from user
    stoploop=0
    #extracts the first two results from API
    if annotations.web_entities:
        name = []
        score = []
        for x in range(0,2):
            name.append(annotations.web_entities[x].description)
            score.append(annotations.web_entities[x].score)
        #creates a new Image node from users' input if it does not exist yet
        exist_image = cypher.execute_one("MATCH (n:Image { url: '" + URL + "'}) RETURN count(*)")
        if exist_image == 0:
            cypher.execute("CREATE (image:Image {url: '" + URL + "'})")
        #creates Page nodes and relationship to just created Image node
        if annotations.pages_with_matching_images:
            for page in annotations.pages_with_matching_images:
                url = format(page.url)
                exist_page = cypher.execute_one("MATCH (n:Page { url: '" + url + "'}) RETURN count(*)")
                if exist_page==0:
                    cypher.execute("CREATE (page:Page {url: '" + url + "'})")
                exist_rel = cypher.execute_one(
                    "MATCH (n:Page { url: '" + url + "'})-[:CONTAIN]->(k:Image{url: '" + URL + "'}) RETURN count(*)")
                if exist_rel == 0:
                    cypher.execute("MATCH (page:Page), (image:Image) WHERE page.url='" + url + "' AND image.url='" + URL + "' CREATE (page)-[:CONTAIN]->(image)")
        #checkes for the same pill in DB
        for x in range(0, 2):
            #checks if program finds pill
            if stoploop==1:
                break
            else:
                #checks for an existinf Pill node with the name of the pill
                check = cypher.execute_one("MATCH (n:Pill { name: '" + name[x] + "'}) RETURN count(*)")
                #if there is no node program creates node and relationship between Image and Pill
                if check==0:
                    cypher.execute("CREATE (pill:Pill {name: '" + name[x] + "'})")
                    cypher.execute("MATCH (image:Image), (pill:Pill) WHERE image.url='" + URL + "' AND pill.name='" + name[x] + "' CREATE (pill)<-[:HAS {score: '" + str(score[x]) + "'}]-(image)")
                #otherwise it returns images from DB
                else:
                    #finds all images which has relationship with pill
                    results = cypher.execute("MATCH (n:Pill { name: '" + name[x] + "'})<-[:HAS]-(b: Image) RETURN b.url as url")
                    #in the first round of loop checks if both names for pill are in DB
                    #if not creates them, creates relationship between pill and image
                    if x==0:
                        for x in range(0, 2):
                            exist_pill = cypher.execute_one("MATCH (n:Pill { name: '" + name[x] + "'}) RETURN count(*)")
                            if exist_pill == 0:
                                cypher.execute("CREATE (page:Pill {name: '" + name[x] + "'})")
                            exist_rel_pill = cypher.execute_one("MATCH (n:Pill { name: '" + name[x] + "'})<-[:HAS]-(g:Image {url: '" + URL + "'}) RETURN count(*)")
                            if exist_rel_pill == 0:
                                cypher.execute("MATCH (image:Image), (pill:Pill) WHERE image.url='" + URL + "' AND pill.name='" + name[x] + "' CREATE (pill)<-[:HAS {score: '" + str(score[x]) + "'}]-(image)")
                    records = [n for n in results]
                    for record in records:
                        same_url=str(record["url"])
                        #checks to not show the image of itself
                        if not same_url==URL:
                            show_result(URL, record["url"])
                            response = pymsgbox.prompt('Your pill is on the left side.\n Does our pill(the right picture) look the same as yours pill?')
                            #if user finds pill as he has program returns name of the pill and breaks
                            if response == "yes":
                                pymsgbox.alert('It is ' + name[0] + ' or ' + name[1])
                                stoploop=1
                                break
    #if there is no identical pill in DB no return
    if stoploop==0:
        pymsgbox.alert('Sorry, there is no such pill in database')

URL1 = fix_url(URL)
report(annotate(URL1))