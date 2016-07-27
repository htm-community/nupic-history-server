# ----------------------------------------------------------------------
# Numenta Platform for Intelligent Computing (NuPIC)
# Copyright (C) 2014, Numenta, Inc.  Unless you have purchased from
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
import os
import shutil



DIRNAME_DIMENSIONS         = "dimensions"
DIRNAME_MODEL_STATES       = "states"
DIRNAME_ENCODERS           = "encoders"

FILENAME_ACTIVE_COLUMNS    = "active_columns.json"
FILENAME_ACTIVE_CELLS      = "active_cells.json"
FILENAME_PREDICTED_CELLS   = "predicted_cells.json"
FILENAME_PROXIMAL_SYNAPSES = "proximal_synapses.json"

# Encoders
FILENAME_ENCODERS = "encoders.json"
FILENAME_INPUT    = "input.json"
FILENAME_OUTPUT   = "output.json"

# Coordinate Encoder
FILENAME_NEIGHBORS          = "neighbors.json"
FILENAME_TOP_W_COORDINATES  = "top_w_coordinates.json"



class Keys:


  def __init__(self):
    pass


  def states(self):
    directory = os.path.join(self.dataDir, DIRNAME_MODEL_STATES)
    return getDirectory(directory)


  def dimensions(self, layer):
    directory = os.path.join(self.dataDir, DIRNAME_DIMENSIONS)

    return getKey(directory, layer + ".json")


  def activeColumns(self, layer, iteration):
    directory = os.path.join(self.dataDir,
                              DIRNAME_MODEL_STATES,
                              str(iteration),
                              layer)

    return getKey(directory, FILENAME_ACTIVE_COLUMNS)


  def activeCells(self, layer, iteration):
    directory = os.path.join(self.dataDir,
                              DIRNAME_MODEL_STATES,
                              str(iteration),
                              layer)

    return getKey(directory, FILENAME_ACTIVE_CELLS)


  def predictedCells(self, layer, iteration):
    directory = os.path.join(self.dataDir,
                              DIRNAME_MODEL_STATES,
                              str(iteration),
                              layer)

    return getKey(directory, FILENAME_PREDICTED_CELLS)


  def proximalSynapses(self, layer, iteration):
    directory = os.path.join(self.dataDir,
                              DIRNAME_MODEL_STATES,
                              str(iteration),
                              layer)

    return getKey(directory, FILENAME_PROXIMAL_SYNAPSES)


  def encoders(self):
    directory = os.path.join(self.dataDir)
    return getKey(directory, FILENAME_ENCODERS)


  def encoderInput(self, name, iteration):
    directory = os.path.join(self.dataDir,
                              DIRNAME_MODEL_STATES,
                              str(iteration),
                              DIRNAME_ENCODERS,
                              name)

    return getKey(directory, FILENAME_INPUT)


  def encoderOutput(self, name, iteration):
    directory = os.path.join(self.dataDir,
                              DIRNAME_MODEL_STATES,
                              str(iteration),
                              DIRNAME_ENCODERS,
                              name)

    return getKey(directory, FILENAME_OUTPUT)


  def coordinateEncoderNeighbors(self, name, iteration):
    directory = os.path.join(self.dataDir,
                              DIRNAME_MODEL_STATES,
                              str(iteration),
                              DIRNAME_ENCODERS,
                              name)

    return getKey(directory, FILENAME_NEIGHBORS)


  def coordinateEncoderTopWCoordinates(self, name, iteration):
    directory = os.path.join(self.dataDir,
                              DIRNAME_MODEL_STATES,
                              str(iteration),
                              DIRNAME_ENCODERS,
                              name)

    return getKey(directory, FILENAME_TOP_W_COORDINATES)



def getKey(directory, filename):
  return "{} {}".format(directory, filename)
