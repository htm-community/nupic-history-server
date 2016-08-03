import time
import json

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


def getSpDetails(requestInput, sp):
  kwargs = {}
  for param in SNAPS.listValues():
    key = "get{}{}".format(param[:1].upper(), param[1:])
    kwargs[key] = param in requestInput and requestInput[param] == "true"
  print kwargs
  state = sp.getState(**kwargs)
  # Compress any SDRs.
  return state


class SPInterface:


  def POST(self):
    global spFacades
    params = json.loads(web.data())
    requestInput = web.input()
    # TODO: Provide an interface to specify what internals should be saved.
    shouldSave = "save" in requestInput \
                  and requestInput["save"] == "true"
    detailedResponse = "detailed" in requestInput \
                  and requestInput["detailed"] == "true"
    sp = SP(**params)
    spFacade = spHistory.create(sp)
    spId = spFacade.getId()
    spFacades[spId] = {
      "save": shouldSave,
      "facade": spFacade
    }

    print "Created SP {} | Saving: {}".format(spId, shouldSave)

    web.header("Content-Type", "application/json")
    payload = {
      "id": spId,
    }
    # We will always return the initial state of columns and overlaps becasue
    # they are cheap. We'll only get the extra internals if
    snapshots = [SNAPS.ACT_COL, SNAPS.OVERLAPS]
    if detailedResponse:
      snapshots += [
        SNAPS.POT_POOLS, SNAPS.CON_SYN, SNAPS.PERMS
      ]
    spState = spFacade.getState(*snapshots)
    for key in spState:
      payload[key] = spState[key]
    return json.dumps(payload)


  def OPTIONS(self):
    return web.ok


  def PUT(self):
    requestStart = time.time()
    requestInput = web.input()
    encoding = web.data()
    stateSnapshots = [
      SNAPS.INPUT,
      SNAPS.ACT_COL,
      SNAPS.OVERLAPS
    ]

    if "getConnectedSynapses" in requestInput \
                  and requestInput["getConnectedSynapses"] == "true":
      stateSnapshots.append(SNAPS.CON_SYN)
    if "potentialPools" in requestInput \
               and requestInput["potentialPools"] == "true":
      stateSnapshots.append(SNAPS.POT_POOLS)

    if "id" not in requestInput:
      print "Request must include a spatial pooler id."
      return web.badrequest()

    spId = requestInput["id"]

    if spId not in spFacades.keys():
      print "Unknown SP id {}!".format(spId)
      return web.badrequest()

    sp = spFacades[spId]["facade"]
    shouldSave = spFacades[spId]["save"]

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
