import sys
import time
import simplejson as json

import numpy as np
import web

from nupic.research.spatial_pooler import SpatialPooler as SP

from nupic_history import SpHistory, SpSnapshots as SNAPS


global spFacades
spFacades = {}
spHistory = SpHistory()

urls = (
  "/", "Index",
  "/client/(.+)", "Client",
  "/_sp/", "SPInterface",
  "/_sp/(.+)/history/(.+)", "History",
)
app = web.application(urls, globals())
render = web.template.render("tmpl/")


def templateNameToTitle(name):
  if name == "index": return ""
  title = name
  if "-" in title:
    title = title.replace("-", " ")
  return title.title()



class Index:


  def GET(self):
    return "NuPIC History Server"


class Client:


  def GET(self, file):
    name = file.split(".")[0]
    path = "html/{}".format(file)
    with open(path, "r") as htmlFile:
      return render.layout(
        name,
        templateNameToTitle(name),
        htmlFile.read()
      )


class SPInterface:


  def POST(self):
    global spFacades
    params = json.loads(web.data())
    requestInput = web.input()
    # We will always return the initial state of columns and overlaps because
    # they are cheap.
    saveSnapshots = [
      SNAPS.ACT_COL,
      SNAPS.OVERLAPS
    ]
    if "save" in requestInput and len(requestInput["save"]) > 0:
      saveSnapshots += [str(s) for s in requestInput["save"].split(",")]
      # Remove duplicates that might have been added in the request.
      saveSnapshots = list(set(saveSnapshots))

    sp = SP(**params)
    spFacade = spHistory.create(sp, save=saveSnapshots)
    spId = spFacade.getId()
    spFacades[spId] = spFacade

    print "Created SP {} | Saving: {}".format(spId, saveSnapshots)

    payload = {
      "meta": {
        "id": spId,
        "saving": saveSnapshots
      }
    }
    spState = spFacade.getState(*saveSnapshots)
    for key in spState:
      payload[key] = spState[key]

    web.header("Content-Type", "application/json")
    return json.dumps(payload)


  def PUT(self):
    requestStart = time.time()
    requestInput = web.input()
    encoding = web.data()
    stateSnapshots = [
      SNAPS.ACT_COL,
    ]

    for snap in SNAPS.listValues():
      getString = "get{}{}".format(snap[:1].upper(), snap[1:])
      if getString in requestInput and requestInput[getString] == "true":
        stateSnapshots.append(snap)

    if "id" not in requestInput:
      print "Request must include a spatial pooler id."
      return web.badrequest()

    spId = requestInput["id"]

    if spId not in spFacades.keys():
      print "Unknown SP id {}!".format(spId)
      return web.badrequest()

    sp = spFacades[spId]

    learn = True
    if "learn" in requestInput:
      learn = requestInput["learn"] == "true"

    inputArray = np.array([int(bit) for bit in encoding.split(",")])

    print "Entering SP compute cycle | Learning: {}".format(learn)
    sp.compute(inputArray, learn=learn)

    response = sp.getState(*stateSnapshots)

    web.header("Content-Type", "application/json")
    jsonOut = json.dumps(response)

    requestEnd = time.time()
    print("\tSP compute cycle took %g seconds" % (requestEnd - requestStart))

    return jsonOut



class History:

  def GET(self, spId, columnIndex):
    sp = spFacades[spId]["facade"]
    permanences = sp.getState(
      SNAPS.PERMS, columnIndex=columnIndex
    )[SNAPS.PERMS]
    connections = sp.getState(
      SNAPS.CON_SYN, columnIndex=columnIndex
    )[SNAPS.CON_SYN]
    return json.dumps({
      "connections": connections,
      "permanences": permanences
    })

if __name__ == "__main__":
  app.run()
