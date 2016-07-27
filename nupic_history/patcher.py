# ----------------------------------------------------------------------
# Numenta Platform for Intelligent Computing (NuPIC)
# Copyright (C) 2016, Numenta, Inc.  Unless you have purchased from
# Numenta, Inc. a separate commercial license for this software code, the
# following terms and conditions apply:
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero Public License for more details.
#
# You should have received a copy of the GNU Affero Public License
# along with this program.  If not, see http://www.gnu.org/licenses.
#
# http://numenta.org/licenses/
# ----------------------------------------------------------------------
import json
import numpy

import redis

from nupic.bindings.math import GetNTAReal

from save_keys import Keys

realType = GetNTAReal()



class Patcher(object):


  def __init__(self, host="localhost", port=6379):
    self.redis = redis.Redis(host, port)
    self.paths = Keys()


  def patchSP(self, sp):
    SPPatch(self).patch(sp)


  def saveDimensions(self, dimensions, layer):
    self.writeJSON(dimensions, self.paths.dimensions(layer))


  def saveActiveColumns(self, activeColumns, layer, iteration):
    self.writeJSON(activeColumns, self.paths.activeColumns(layer, iteration))


  def saveActiveCells(self, activeCells, layer, iteration):
    self.writeJSON(activeCells, self.paths.activeCells(layer, iteration))


  def savePredictedCells(self, predictedCells, layer, iteration):
    self.writeJSON(predictedCells, self.paths.predictedCells(layer, iteration))


  def saveProximalSynapses(self, proximalSynapses, layer, iteration):
    self.writeJSON(proximalSynapses, self.paths.proximalSynapses(layer, iteration))



class Patch(object):


  def __init__(self, patcher):
    self.patcher = patcher
    self.iteration = 1



class SPPatch(Patch):


  def patch(self, sp, keysToSave):
    self.sp = sp
    self.keysToSave = keysToSave
    self.saveInputDimensions()
    self.saveColumnDimensions()

    compute = sp.compute

    def patchedCompute(inputVector, learn, activeArray, *args, **kwargs):
      results = compute(inputVector, learn, activeArray, *args, **kwargs)
      self.saveState(inputVector, activeArray)
      self.iteration += 1
      return results

    sp.compute = patchedCompute



  def saveInputDimensions(self):
    dimensions = list(self.sp.getInputDimensions())
    self.patcher.saveDimensions(dimensions, "input")


  def saveColumnDimensions(self):
    dimensions = list(self.sp.getColumnDimensions())
    self.patcher.saveDimensions(dimensions, "output")


  def saveState(self, inputVector, activeArray):
    activeCells = inputVector.nonzero()[0].tolist()
    self.patcher.saveActiveCells(activeCells, "input", self.iteration)

    activeColumns = activeArray.nonzero()[0].tolist()
    self.patcher.saveActiveColumns(activeColumns, "output", self.iteration)

    numColumns = self.sp.getNumColumns()
    numInputs = self.sp.getNumInputs()
    permanence = numpy.zeros(numInputs).astype(realType)
    proximalSynapses = []

    """ Proximal synapses storage format:
        A list of proximal connections, each represented by a list: [toIndex, fromIndex, permanence]
            ...where fromIndex is the index of a cell in the input layer,
                     toIndex is the index of a column in the SP layer,
                     permanence is the permanence value of the proximal connection.
    """
    for column in range(numColumns):
      self.sp.getPermanence(column, permanence)

      for input in permanence.nonzero()[0]:  # TODO: can this be optimized?
        proximalSynapses.append([column, input, permanence[input].tolist()])

    self.patcher.saveProximalSynapses(proximalSynapses, "output", self.iteration)


  def writeJSON(self, obj, key):
    payload = json.dumps(obj, cls=NumpyAwareJSONEncoder)
    self.redis.set(key, payload)



  def readJSON(self, key):
    payload = self.redis.get(key)
    return json.loads(payload)



class NumpyAwareJSONEncoder(json.JSONEncoder):
  def default(self, obj):
    if isinstance(obj, numpy.ndarray):
      return obj.tolist()
    return json.JSONEncoder.default(self, obj)
