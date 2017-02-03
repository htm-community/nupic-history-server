import time
import simplejson as json
import uuid

import numpy as np
import web

from nupic.research.spatial_pooler import SpatialPooler as SP
from nupic.research.temporal_memory import TemporalMemory as TM

from nupic_history import NupicHistory
from nupic_history import SpSnapshots as SP_SNAPS
from nupic_history.redis_client import FileIoClient
from nupic_history.sp_facade import SpFacade
from nupic_history import TmSnapshots as TM_SNAPS
from nupic.algorithms.sdr_classifier_factory import SDRClassifierFactory


redisClient = FileIoClient(workingDir="./working")

tmFacades = {}
classifiers = {}
counts = {}
nupicHistory = NupicHistory()

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
    requestPayload = json.loads(web.data())
    params = requestPayload["params"]
    states = requestPayload["states"]

    from pprint import pprint; pprint(params)
    sp = SpFacade(SP(**params), redisClient)
    sp.save()

    payload = {
      "id": sp.getId(),
      "iteration": -1,
      "state": {}
    }
    payload["state"] = sp.getState(*states)

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
    requestStart = time.time()
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

    learn = True
    if "learn" in requestPayload:
      learn = requestPayload["learn"]

    # TODO: check for missing modelId and return bad request.

    sp = SpFacade(modelId, redisClient)
    iteration = sp.getIteration()
    inputArray = np.array(encoding)

    print "Entering SP {} compute cycle | Learning: {}".format(modelId, learn)
    sp.compute(inputArray, learn=learn)

    # This is important. It is the one and only place that should be ticking
    # the counter forward (right before saving).
    iteration += 1
    sp.save()

    response = {}
    response["iteration"] = iteration
    response["id"] = modelId
    print requestedStates
    response["state"] = sp.getState(*requestedStates)

    web.header("Content-Type", "application/json")
    jsonOut = json.dumps(response)

    requestEnd = time.time()
    print("\tSP compute cycle took %g seconds" % (requestEnd - requestStart))

    return jsonOut



# class SpHistoryRoute:
#
#   def GET(self, modelId, columnIndex):
#     """
#     Returns entire history of SP for given column
#     """
#     sp = spFacades[modelId]
#     history = sp.getState(
#       SP_SNAPS.PERMS, SP_SNAPS.ACT_COL, columnIndex=int(columnIndex)
#     )
#     return json.dumps(history)
#
#
#
# class TmRoute:
#
#
#   def POST(self):
#     global tmFacades
#     params = json.loads(web.data())
#     requestInput = web.input()
#     # We will always return the active cells because they are cheap.
#     returnSnapshots = [TM_SNAPS.ACT_CELLS]
#     saveSnapshots = []
#     if __name__ == '__main__':
#       if "save" in requestInput and len(requestInput["save"]) > 0:
#         saveSnapshots += [str(s) for s in requestInput["save"].split(",")]
#         # Be sure to also return any snapshots that were specified to be saved.
#         returnSnapshots += saveSnapshots
#         # Remove potential duplicates from both
#         returnSnapshots = list(set(returnSnapshots))
#         saveSnapshots = list(set(saveSnapshots))
#     from pprint import pprint; pprint(params)
#     tm = TM(**params)
#     tmFacade = nupicHistory.createTmFacade(
#       tm, save=saveSnapshots, modelId=requestInput["id"]
#     )
#     modelId = tmFacade.getId()
#     tmFacades[modelId] = tmFacade
#     classifiers[modelId] = SDRClassifierFactory.create()
#     counts[modelId] = 0
#
#     print "Created TM {} | Saving: {}".format(modelId, saveSnapshots)
#
#     payload = {
#       "meta": {
#         "id": modelId,
#         "saving": returnSnapshots
#       }
#     }
#     tmState = tmFacade.getState(*returnSnapshots)
#     for key in tmState:
#       payload[key] = tmState[key]
#
#     web.header("Content-Type", "application/json")
#     return json.dumps(payload)
#
#
#   def PUT(self):
#     requestStart = time.time()
#     requestInput = web.input()
#     encoding = web.data()
#     stateSnapshots = [
#       TM_SNAPS.ACT_CELLS,
#       TM_SNAPS.PRD_CELLS,
#     ]
#
#     for snap in TM_SNAPS.listValues():
#       getString = "get{}{}".format(snap[:1].upper(), snap[1:])
#       if getString in requestInput and requestInput[getString] == "true":
#         stateSnapshots.append(snap)
#
#     if "id" not in requestInput:
#       print "Request must include a model id."
#       return web.badrequest()
#
#     modelId = requestInput["id"]
#
#     if modelId not in tmFacades.keys():
#       print "Unknown model id {}!".format(modelId)
#       return web.badrequest()
#
#     tm = tmFacades[modelId]
#
#     learn = True
#     if "learn" in requestInput:
#       learn = requestInput["learn"] == "true"
#     reset = False
#     if "reset" in requestInput:
#       reset = requestInput["reset"] == "true"
#
#     inputArray = np.array([])
#     if len(encoding):
#       inputArray = np.array([int(bit) for bit in encoding.split(",")])
#
#     print "Entering TM {} compute cycle | Learning: {}".format(modelId, learn)
#     tm.compute(inputArray.tolist(), learn=learn)
#
#     response = tm.getState(*stateSnapshots)
#
#     if reset:
#       print "Resetting TM."
#       tm.reset()
#
#     web.header("Content-Type", "application/json")
#     jsonOut = json.dumps(response)
#
#     requestEnd = time.time()
#     print("\tTM compute cycle took %g seconds" % (requestEnd - requestStart))
#
#     return jsonOut
#
#
# class ComputeRoute:
#
#   def PUT(self):
#     requestStart = time.time()
#     requestInput = web.input()
#     encoding = web.data()
#     spSnapshots = [
#       SP_SNAPS.ACT_COL,
#     ]
#     tmSnapshots = [
#       TM_SNAPS.ACT_CELLS,
#       TM_SNAPS.PRD_CELLS,
#     ]
#
#     for snap in SP_SNAPS.listValues():
#       getString = "get{}{}".format(snap[:1].upper(), snap[1:])
#       if getString in requestInput and requestInput[getString] == "true":
#         spSnapshots.append(snap)
#
#     for snap in TM_SNAPS.listValues():
#       getString = "get{}{}".format(snap[:1].upper(), snap[1:])
#       if getString in requestInput and requestInput[getString] == "true":
#         tmSnapshots.append(snap)
#
#     if "id" not in requestInput:
#       print "Request must include a model id."
#       return web.badrequest()
#
#     modelId = requestInput["id"]
#
#     if modelId not in spFacades.keys():
#       print "Unknown SP id {}!".format(modelId)
#       return web.badrequest()
#
#     sp = spFacades[modelId]
#
#     spLearn = True
#     if "spLearn" in requestInput:
#       spLearn = requestInput["spLearn"] == "true"
#
#     inputArray = np.array([])
#     if len(encoding):
#       inputArray = np.array([int(bit) for bit in encoding.split(",")])
#
#     print "Entering SP {} compute cycle | Learning: {}".format(modelId, spLearn)
#     sp.compute(inputArray, learn=spLearn)
#     spResults = sp.getState(*spSnapshots)
#     activeColumns = spResults[SP_SNAPS.ACT_COL]['indices']
#
#     tm = tmFacades[modelId]
#
#     tmLearn = True
#     if "tmLearn" in requestInput:
#       tmLearn = requestInput["tmLearn"] == "true"
#
#     reset = False
#     if "reset" in requestInput:
#       reset = requestInput["reset"] == "true"
#
#     print "Entering TM {} compute cycle | Learning: {}".format(modelId, tmLearn)
#     tm.compute(activeColumns, learn=tmLearn)
#
#     tmResults = tm.getState(*tmSnapshots)
#
#     c = classifiers[modelId]
#     bucketIdx = requestInput["bucketIdx"]
#     actValue = requestInput["actValue"]
#     count = counts[modelId]
#
#     # inference
#     inference = c.compute(
#       recordNum=count, patternNZ=tmResults[TM_SNAPS.ACT_CELLS],
#       classification={"bucketIdx": bucketIdx, "actValue": actValue},
#       learn=True, infer=True
#     )
#
#     # Print the top three predictions for 1 steps out.
#     topPredictions = sorted(
#       zip(
#         inference[1], inference["actualValues"]
#       ), reverse=True
#     )[:3]
#     for probability, value in topPredictions:
#       print "Prediction of {} has probability of {}.".format(
#         value, probability*100.0
#       )
#
#     if reset:
#       print "Resetting TM."
#       tm.reset()
#
#     completeResults = {}
#     completeResults.update(spResults)
#     completeResults.update(tmResults)
#     completeResults["inference"] = topPredictions
#
#     web.header("Content-Type", "application/json")
#     jsonOut = json.dumps(completeResults)
#
#     requestEnd = time.time()
#     print("\tFULL compute cycle took %g seconds" % (requestEnd - requestStart))
#
#     counts[modelId] += 1
#
#     return jsonOut


class RoyalFlush:


  def DELETE(self):
    redisClient.nuke()
    return "NuPIC History Server got NUKED!"



if __name__ == "__main__":
  app.run()
