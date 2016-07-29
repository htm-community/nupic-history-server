import time
import json

import numpy as np
import web

from nupic.research.spatial_pooler import SpatialPooler as SP

from nupic_history import SpHistory, SpSnapshots


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
  for param in SpSnapshots.listValues():
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
    shouldSave = "save" in requestInput \
                  and requestInput["save"] == "true"
    sp = SP(**params)
    spFacade = spHistory.create(sp)
    spId = spFacade.getId()
    spFacades[spId] = {
      "save": shouldSave,
      "facade": spFacade
    }
    web.header("Content-Type", "application/json")
    # Send back the SP id and any details about the initial state that the client
    # specified in the request's URL params.
    payload = {
      "id": spId,
    }
    spState = getSpDetails(requestInput, spFacade)
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
      SpSnapshots.INPUT,
      SpSnapshots.ACT_COL,
      SpSnapshots.OVERLAPS
    ]

    if "getConnectedSynapses" in requestInput \
                  and requestInput["getConnectedSynapses"] == "true":
      stateSnapshots.append(SpSnapshots.CON_SYN)
    if "potentialPools" in requestInput \
               and requestInput["potentialPools"] == "true":
      stateSnapshots.append(SpSnapshots.POT_POOLS)

    if "id" not in requestInput:
      print "Request must include a spatial pooler id."
      return web.badrequest()

    spId = requestInput["id"]

    if spId not in spFacades:
      print "Unknown SP id {}!".format(spId)
      return web.badrequest()

    sp = spFacades[spId]["facade"]
    shouldSave = spFacades[spId]["save"]

    learn = True
    if "learn" in requestInput:
      learn = requestInput["learn"] == "true"

    inputArray = np.array([int(bit) for bit in encoding.split(",")])

    print "Entering SP compute cycle | Learning: {}".format(learn)
    sp.compute(inputArray, learn=learn, save=shouldSave)

    response = sp.getState(*stateSnapshots)

    web.header("Content-Type", "application/json")
    jsonOut = json.dumps(response)

    requestEnd = time.time()
    print("\tSP compute cycle took %g seconds" % (requestEnd - requestStart))

    return jsonOut



class History:

  def GET(self, spId, columnIndex):
    sp = spFacades[spId]
    connections = sp.getConnectionHistoryForColumn(columnIndex)
    permanences = sp.getPermanenceHistoryForColumn(columnIndex)
    return json.dumps({
      "connections": connections,
      "permanences": permanences
    })

if __name__ == "__main__":
  app.run()
