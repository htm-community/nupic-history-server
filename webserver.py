import time
import ujson as json
import uuid

import numpy as np
import web

cpp = True

if cpp:
  from nupic.bindings.algorithms import SpatialPooler as SP
else:
  from nupic.research.spatial_pooler import SpatialPooler as SP

from nupic.bindings.algorithms import TemporalMemory as TM

from nupic_history import NupicHistory
from nupic_history import SpSnapshots as SP_SNAPS
from nupic_history.io_client import FileIoClient
from nupic_history.sp_facade import SpFacade
from nupic_history.tm_facade import TmFacade
from nupic_history import TmSnapshots as TM_SNAPS
from nupic.algorithms.sdr_classifier_factory import SDRClassifierFactory


ioClient = FileIoClient(workingDir="./working")
modelCache = {}
nupicHistory = NupicHistory(ioClient)

urls = (
  "/", "Index",
  "/_sp/", "SpRoute",
  "/_sp/(.+)/history/(.+)", "SpHistoryRoute",
  "/_tm/", "TmRoute",
  "/_compute/", "ComputeRoute",
  "/_flush/", "RoyalFlush",
)
web.config.debug = False
app = web.application(urls, globals())



class Index:


  def GET(self):
    return "NuPIC History Server"


class SpRoute:


  def POST(self):
    """
    Creates a new Spatial Pooler with a unique ID.

    No URL params expected.

    POST params:

    states: (string array):  List of the SP states you want back. Active columns
                             are always sent. Otherwise, you can find a list of
                             available states in snapshots.py.

    :return: requested state from the sp instance in JSON, keyed by strings in
             POST "states" param.
    """
    global modelCache
    requestPayload = json.loads(web.data())
    params = requestPayload["params"]
    states = requestPayload["states"]
    save = requestPayload["save"]

    from pprint import pprint; pprint(params)
    sp = SpFacade(SP(**params), ioClient)

    modelId = sp.getId()

    payload = {
      "id": modelId,
      "iteration": -1,
      "state": {}
    }
    payload["state"] = sp.getState(*states)

    if save:
      print "\tSaving SP {} to disk...".format(modelId)
      sp.save()

    print "\tSaving SP {} to memory...".format(modelId)
    modelCache[modelId] = {
      "sp": sp,
      "save": save,
    }

    web.header("Content-Type", "application/json")
    return json.dumps(payload)


  def PUT(self):
    """
    Runs a row of binary input into a Spatial Pooler by id. This method should
    not be used for history extraction, only for running new data.

    No URL params expected.

    POST params:

    id (string):             The model ID you got when you created the SP.
    encoding (binary array): Semantic encoding of 1s and 0s. No dimensional
                             checking is done. It is passed as-is into the
                             spatial pooler.
    learn ('true'|'false'):  Should the Spatial Pooler mutate permanence values?
    states: (string array):  List of the SP states you want back. Active columns
                             are always sent. Otherwise, you can find a list of
                             available states in snapshots.py.

    :return: id, iteration, and requested state from the sp instance in JSON.
             States are keyed by strings given in POST "states" param.
    """
    start = time.time()
    requestPayload = json.loads(web.data())

    if "id" not in requestPayload:
      print "Request must include a model id for Spatial Pooler retrieval."
      return web.badrequest()
    if "encoding" not in requestPayload:
      print "Request must include an encoding."
      return web.badrequest()

    modelId = requestPayload["id"]
    encoding = requestPayload["encoding"]

    requestedStates = []
    if "states" in requestPayload:
      requestedStates = requestPayload["states"]

    learn = False
    if "learn" in requestPayload and requestPayload["learn"] == "true":
      learn = True

    if modelId in modelCache.keys():
      print "\tFetching SP {} from memory...".format(modelId)
      sp = modelCache[modelId]["sp"]
      save = modelCache[modelId]["save"]
    else:
      print "\tFetching SP {} from disk...".format(modelId)
      sp = SpFacade(modelId, ioClient)
      sp.load()
      save = True

    iteration = sp.getIteration()

    print "\tEntering SP {} compute cycle iteration {} (Learn: {} Save: {})"\
      .format(modelId, iteration, learn, save)
    sp.compute(encoding, learn=learn, save=save, multiprocess=True)

    response = {}
    response["iteration"] = iteration
    response["id"] = modelId
    response["state"] = sp.getState(*requestedStates)

    web.header("Content-Type", "application/json")
    jsonOut = json.dumps(response)

    end = time.time()
    print("\tHTTP SP compute cycle took %g seconds" % (end - start))

    return jsonOut



class SpHistoryRoute:

  def GET(self, modelId, columnIndex):
    """
    Returns entire history of SP for given column
    """
    requestInput = web.input()
    states = requestInput["states"].split(',')

    if modelId in modelCache.keys():
      print "Fetching SP {} from memory...".format(modelId)
      sp = modelCache[modelId]["sp"]
    else:
      try:
        print "Fetching SP {} from disk...".format(modelId)
        sp = SpFacade(modelId, ioClient)
      except:
        print "Unknown model id: {}".format(modelId)
        return web.badrequest()

    history = nupicHistory.getColumnHistory(modelId, int(columnIndex), states)

    return json.dumps(history)



class TmRoute:


  def POST(self):
    global modelCache
    params = json.loads(web.data())
    requestInput = web.input()
    id = requestInput["id"]
    # We will always return the active cells because they are cheap.
    returnSnapshots = [TM_SNAPS.ACT_CELLS]
    from pprint import pprint; pprint(params)
    tm = TM(**params)

    tmFacade = TmFacade(tm, ioClient, modelId=id)

    modelId = tmFacade.getId()
    modelCache[modelId]["tm"] = tmFacade
    modelCache[modelId]["classifier"] = SDRClassifierFactory.create(implementation="py")
    modelCache[modelId]["recordsSeen"] = 0

    print "Created TM {}".format(modelId)

    payload = {
      "meta": {
        "id": modelId,
        "saving": returnSnapshots
      }
    }

    tmState = tmFacade.getState(*returnSnapshots)

    for key in tmState:
      payload[key] = tmState[key]

    web.header("Content-Type", "application/json")
    return json.dumps(payload)


  def PUT(self):
    requestStart = time.time()
    requestInput = web.input()
    encoding = web.data()
    stateSnapshots = [
      TM_SNAPS.ACT_CELLS,
      TM_SNAPS.PRD_CELLS,
    ]

    for snap in TM_SNAPS.listValues():
      getString = "get{}{}".format(snap[:1].upper(), snap[1:])
      if getString in requestInput and requestInput[getString] == "true":
        stateSnapshots.append(snap)

    if "id" not in requestInput:
      print "Request must include a model id."
      return web.badrequest()

    modelId = requestInput["id"]

    if modelId not in tmFacades.keys():
      print "Unknown model id {}!".format(modelId)
      return web.badrequest()

    tm = tmFacades[modelId]

    learn = True
    if "learn" in requestInput:
      learn = requestInput["learn"] == "true"
    reset = False
    if "reset" in requestInput:
      reset = requestInput["reset"] == "true"

    inputArray = np.array([])
    if len(encoding):
      inputArray = np.array([int(bit) for bit in encoding.split(",")])

    print "Entering TM {} compute cycle | Learning: {}".format(modelId, learn)
    tm.compute(inputArray.tolist(), learn=learn)

    response = tm.getState(*stateSnapshots)

    if reset:
      print "Resetting TM."
      tm.reset()

    web.header("Content-Type", "application/json")
    jsonOut = json.dumps(response)

    requestEnd = time.time()
    print("\tTM compute cycle took %g seconds" % (requestEnd - requestStart))

    return jsonOut


class ComputeRoute:

  def PUT(self):
    requestStart = time.time()
    requestInput = web.input()
    encoding = web.data()
    spSnapshots = [
      SP_SNAPS.ACT_COL,
    ]
    tmSnapshots = [
      TM_SNAPS.ACT_CELLS,
      TM_SNAPS.PRD_CELLS,
    ]

    for snap in SP_SNAPS.listValues():
      getString = "get{}{}".format(snap[:1].upper(), snap[1:])
      if getString in requestInput and requestInput[getString] == "true":
        spSnapshots.append(snap)

    for snap in TM_SNAPS.listValues():
      getString = "get{}{}".format(snap[:1].upper(), snap[1:])
      if getString in requestInput and requestInput[getString] == "true":
        tmSnapshots.append(snap)

    if "id" not in requestInput:
      print "Request must include a model id."
      return web.badrequest()

    modelId = requestInput["id"]

    if modelId not in modelCache.keys():
      print "Unknown Model id {}!".format(modelId)
      return web.badrequest()

    sp = modelCache[modelId]["sp"]

    spLearn = True
    if "spLearn" in requestInput:
      spLearn = requestInput["spLearn"] == "true"

    inputArray = np.array([])
    if len(encoding):
      inputArray = np.array([int(bit) for bit in encoding.split(",")])

    print "Entering SP {} compute cycle | Learning: {}".format(modelId, spLearn)
    sp.compute(inputArray, learn=spLearn)
    spResults = sp.getState(*spSnapshots)
    activeColumns = spResults[SP_SNAPS.ACT_COL]['indices']

    tm = modelCache[modelId]["tm"]

    tmLearn = True
    if "tmLearn" in requestInput:
      tmLearn = requestInput["tmLearn"] == "true"

    reset = False
    if "reset" in requestInput:
      reset = requestInput["reset"] == "true"

    print "Entering TM {} compute cycle | Learning: {}".format(modelId, tmLearn)
    tm.compute(activeColumns, learn=tmLearn)

    tmResults = tm.getState(*tmSnapshots)

    c = modelCache[modelId]["classifier"]
    bucketIdx = int(requestInput["bucketIdx"])
    actValue = requestInput["actValue"]
    recordNum = int(modelCache[modelId]["recordsSeen"])

    # inference
    inference = c.compute(
      recordNum=recordNum, patternNZ=tmResults[TM_SNAPS.ACT_CELLS],
      classification={"bucketIdx": bucketIdx, "actValue": actValue},
      learn=True, infer=True
    )

    # Print the top three predictions for 1 steps out.
    topPredictions = sorted(
      zip(
        inference[1], inference["actualValues"]
      ), reverse=True
    )[:3]
    for probability, value in topPredictions:
      print "Prediction of {} has probability of {}.".format(
        value, probability*100.0
      )

    if reset:
      print "Resetting TM."
      tm.reset()

    completeResults = {}
    completeResults.update(spResults)
    completeResults.update(tmResults)
    completeResults["inference"] = topPredictions

    web.header("Content-Type", "application/json")
    jsonOut = json.dumps(completeResults)

    requestEnd = time.time()
    print("\tFULL compute cycle took %g seconds" % (requestEnd - requestStart))

    modelCache[modelId]["recordsSeen"] += 1

    return jsonOut


class RoyalFlush:


  def DELETE(self):
    global modelCache
    ioClient.nuke()
    modelCache = {}
    return "NuPIC History Server got NUKED!"



if __name__ == "__main__":
  app.run()
