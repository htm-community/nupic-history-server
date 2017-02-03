import uuid


def createSpatialPooler(streamIds, **kwargs):
  """
  Creates and loads data into a Confluence, which is a collection of River
  Streams.
  :param streamIds: (list) Each data id in this list is a list of strings:
                    1. river name
                    2. stream name
                    3. field name
  :param kwargs: Passed into Confluence constructor
  :return: (Confluence)
  """
  print "Creating Confluence for the following RiverStreams:" \
        "\n\t%s" % ",\n\t".join([":".join(row) for row in streamIds])
  confluence = Confluence(streamIds, **kwargs)
  confluence.load()
  return confluence


