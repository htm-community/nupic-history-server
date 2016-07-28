from nupic_history import SpHistory


spHistory = SpHistory()



def runRetrieveTest():
  spFacades = spHistory.list()
  if len(spFacades) == 0:
    print "There is no SP history saved."
    return
  print "Found {} SP Facades:".format(len(spFacades))
  for sp in spFacades:
    print str(sp)


if __name__ == "__main__":
  runRetrieveTest()
