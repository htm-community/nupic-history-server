import time
import simplejson as json

import numpy as np
import web

from nupic.research.spatial_pooler import SpatialPooler as SP

from nupic_history import SpRedisClient, SpHistory, SpSnapshots as SNAPS

global spFacades
spFacades = {}
spHistory = SpHistory()

urls = (
  "/", "Index",
  "/client/(.+)", "Client",
  "/_sp/", "SPInterface",
  "/_sp/(.+)/history/(.+)", "History",
)
web.config.debug = False
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
    returnSnapshots = [
      SNAPS.ACT_COL,
      SNAPS.OVERLAPS
    ]
    saveSnapshots = []
    if __name__ == '__main__':
      if "save" in requestInput and len(requestInput["save"]) > 0:
        saveSnapshots += [str(s) for s in requestInput["save"].split(",")]
        # Be sure to also return any snapshots that were specified to be saved.
        returnSnapshots += saveSnapshots
        # Remove potential duplicates from both
        returnSnapshots = list(set(returnSnapshots))
        saveSnapshots = list(set(saveSnapshots))

    sp = SP(**params)
    spFacade = spHistory.create(sp, save=saveSnapshots)
    spId = spFacade.getId()
    spFacades[spId] = spFacade

    print "Created SP {} | Saving: {}".format(spId, saveSnapshots)

    payload = {
      "meta": {
        "id": spId,
        "saving": returnSnapshots
      }
    }
    spState = spFacade.getState(*returnSnapshots)
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

    spid = requestInput["id"]

    if spid not in spFacades.keys():
      print "Unknown SP id {}!".format(spid)
      return web.badrequest()

    sp = spFacades[spid]

    learn = True
    if "learn" in requestInput:
      learn = requestInput["learn"] == "true"

    inputArray = np.array([int(bit) for bit in encoding.split(",")])

    print "Entering SP {} compute cycle | Learning: {}".format(spid, learn)
    sp.compute(inputArray, learn=learn)

    response = sp.getState(*stateSnapshots)

    web.header("Content-Type", "application/json")
    jsonOut = json.dumps(response)

    requestEnd = time.time()
    print("\tSP compute cycle took %g seconds" % (requestEnd - requestStart))

    return jsonOut



class History:

  def GET(self, spId, columnIndex):
    sp = spFacades[spId]
    history = sp.getState(
      SNAPS.PERMS, columnIndex=int(columnIndex)
    )
    return json.dumps(history)

if __name__ == "__main__":
  SpRedisClient().nuke()
  app.run()
