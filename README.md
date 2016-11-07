> ## Work In Progress!
> This project is under very heavy development and will change drastically with no warning.

# NuPIC History Server

> Runs NuPIC behind a web server, exposing internals. For [HTM School visualizations](https://github.com/htm-community/htm-school-viz).

I'm building this to have a consistent HTTP server protocol that will run HTM components, save their states over time, and expose the internal state to web clients.

This relies very heavily on Redis as an in-memory cache (instead of using web sessions). The nice thing is that the history can be maintained in Redis and replayed after the web server has been restarted.

## Installing

> This project generally runs on tip of master in NuPIC, so you need:
> 
> - nupic==0.5.7.dev0
> - nupic.bindings==0.4.13.dev0

Install python requirements.

    pip install -r requirements.txt

Run Redis.

    redis-server

By default, the Redis connection uses `localhost:6379`. I should allow users to override this.

## Save SP State Over Time

If you have an instance of the NuPIC [`SpatialPooler`](https://github.com/numenta/nupic/blob/master/src/nupic/research/spatial_pooler.py#L97), you can create an `SpFacade` object with it. The `SpFacade` will allow you to save the internal state of the spatial pooler at every compute cycle.

```python
# Create a SpatialPooler instance.
sp = nupic.research.spatial_pooler.SpatialPooler(
  inputDimensions=(inputSize,),
  columnDimensions=(outputSize,),
  potentialRadius=16,
  potentialPct=0.85,
  globalInhibition=True,
  localAreaDensity=-1.0,
  numActiveColumnsPerInhArea=40.0,
  stimulusThreshold=1,
  synPermInactiveDec=0.008,
  synPermActiveInc=0.05,
  synPermConnected=0.10,
  minPctOverlapDutyCycle=0.001,
  minPctActiveDutyCycle=0.001,
  dutyCyclePeriod=1000,
  maxBoost=2.0,
  seed=-1,
  spVerbosity=0,
  wrapAround=True
)

# Create the top-level NupicHistory object.
spHistory = NupicHistory()

# Decide what data you want to snapshot. Each one is optional.
snapshots = [
  Snapshots.INPUT,        # input encoding
  Snapshots.ACT_COL,      # active columns
  Snapshots.PERMS,        # permanences for each column to the input space
  Snapshots.CON_SYN,      # connected synapses for each column
                            #   (computed from permanences, not actually saved)
  Snapshots.OVERLAPS,     # overlaps for each column
  Snapshots.ACT_DC,       # active duty cycles
  Snapshots.OVP_DC,       # overlap duty cycles
  Snapshots.POT_POOLS,    # potential pools for each column
]

# Create a facade around the SP that saves history as it runs.
sp = spHistory.create(sp, save=snapshots)

# Feed in 10 random encodings with 10% sparsity.
for _ in range(0, 10):
  encoding = np.zeros(shape=(inputSize,))
  for j, _ in enumerate(encoding):
    if random() < 0.1:
      encoding[j] = 1
  # Each compute cycle will save the specified snapshots into Redis.
  sp.compute(encoding, learn=True)

# This SP's history can be retrieved later through this id:
spid = sp.getId()
```

Now this SP's state has been saved for 10 iterations. Using the returned ID, we can retrieve it later and walk through each iteration with complete access to the SP's internals.

```python
sp = spHistory.get(spid)

# The last iteration the SP saw is still available within its state.
lastIteration = sp.getIteration()

# We can playback the life of the SP.
for i in range(0, lastIteration + 1):
  print "\niteration {}".format(i)
  # We're just printing the keys here, because some of these objects are very
  # large.
  input             = sp.getState(Snapshots.INPUT, iteration=i)
  activeColumns     = sp.getState(Snapshots.ACT_COL, iteration=i)
  potentialPools    = sp.getState(Snapshots.POT_POOLS, iteration=i)
  overlaps          = sp.getState(Snapshots.OVERLAPS, iteration=i)
  permanences       = sp.getState(Snapshots.PERMS, iteration=i)
  activeDutyCycles  = sp.getState(Snapshots.ACT_DC, iteration=i)
  overlapDutyCycles = sp.getState(Snapshots.OVP_DC, iteration=i)
  connectedSynapses = sp.getState(Snapshots.CON_SYN, iteration=i)

# We can also get the history of only one column
# (for permanences, connected synapses)
column42PermHistory = sp.getState(Snapshots.PERMS, column=42)
```
