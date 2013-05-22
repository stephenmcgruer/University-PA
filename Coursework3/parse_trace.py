"""The main driver to parse trace files and simulate their contents."""


import caching
import buses
import itertools
import optparse
import statistics


class SimulationEnvironment:
  """Represents a simulation of a set of caches and a bus.

  The simulation is able to parse a trace file and simulate its contents."""

  # The default values for write buffer size and retire-at count.
  _DEFAULT_WRITE_BUFFER_SIZE = 32
  _DEFAULT_RETIRE_AT_COUNT = 1

  # The set of inconsistent cache line states for a given memory block across
  # two caches.
  INCONSISTENT_STATES = [
    (caching.SlotState.MODIFIED, caching.SlotState.MODIFIED),
    (caching.SlotState.MODIFIED, caching.SlotState.SHARED),
    (caching.SlotState.SHARED, caching.SlotState.MODIFIED)
  ]

  def __init__(self, number_processors, number_lines, line_size,
      consistency_model, write_buffer_size=None, retire_at_count=None,
      debug_mode=False):
    """Initializes the simulation, setting up the bus and caches."""

    self.debug_mode = debug_mode

    self.tracker = statistics.SimulationStatisticsTracker()
    bus = buses.Bus()

    if write_buffer_size is None:
      write_buffer_size = SimulationEnvironment._DEFAULT_WRITE_BUFFER_SIZE

    if retire_at_count is None:
      retire_at_count = SimulationEnvironment._DEFAULT_RETIRE_AT_COUNT

    # Set up the caches. Each cache will register itself with the bus.
    self.caches = []
    for cache_id in xrange(number_processors):
      cache = self._create_cache(cache_id, number_lines, line_size, bus,
          self.tracker, consistency_model, write_buffer_size, retire_at_count,
          debug_mode)
      self.caches.append(cache)

  def simulate(self, trace_filename):
    """Parses a trace, and simulates its contents.

    The trace is retrieved from the file named in the trace_filename
    argument."""

    with open(trace_filename, "r") as trace_file:
      for line in trace_file:
        # Get rid of any comments.
        line = line.split("#")[0].strip()
        if len(line) == 0:
          # Comment line, skip.
          continue

        parts = line.split()

        cache_id = int(parts[0][1:])
        access_type = parts[1]
        address = int(parts[2])

        if access_type == "R":
          self.caches[cache_id].read(address)
        elif access_type == "W":
          self.caches[cache_id].write(address)
        else:
          print "ERROR: Unknown access type '%s'" % access_type
          return

        # Sanity check. Early exit means we dont call the expensive
        # _test_consistency unless in debug mode.
        if self.debug_mode and not self._test_consistency():
          print "ERROR: Caches inconsistent."
          return

    # Notify the caches that the program is finished: used for draining.
    for cache in self.caches:
      cache.notify_finished()

  def report_stats(self):
    """Prints out statistics on the simulation."""

    # The header.
    print "-" * 21
    print "Simulation Statistics"
    print "-" * 21
    print

    # Print the latency statistics.
    stats = self.tracker.get_general_stats()

    max_latency = stats["max_latency"]
    max_latency_cache = stats["max_latency_cache"]

    write_buffer_drains = stats["write_buffer_drains"]
    average_writes_drained = stats["average_writes_drained"]

    mean_latency_between_writes = stats["mean_latency_between_writes"]
    median_latency_between_writes = stats["median_latency_between_writes"]

    write_buffer_snoops = stats["write_buffer_snoops"]

    print "Latency Statistics"
    print

    print("\tProgram latency: {0} cycles (cache {1})".format(max_latency,
        max_latency_cache))

    print("\tWrite buffer drains: {0}".format(write_buffer_drains))
    print("\tAverage writes drained: {0:.2f}".format(average_writes_drained))

    print("\tMean latency between writes: {0}".format(
        mean_latency_between_writes))
    print("\tMedian latency between writes: {0}".format(
        median_latency_between_writes))

    print("\tWrite buffer snoops: {0}".format(write_buffer_snoops))

  def _create_cache(self, cache_id, number_lines, line_size, bus, tracker,
      consistency_model, write_buffer_size, retire_at_count, debug_mode):
    """Creates and returns a cache based on the consistency model."""

    if consistency_model == "SC":
      return caching.Cache(cache_id, number_lines, line_size, bus, tracker,
          debug_mode)
    elif consistency_model == "TSO":
      return caching.TSOCache(cache_id, number_lines, line_size, bus, tracker,
          write_buffer_size, retire_at_count, debug_mode)
    else:
      raise ValueError("Unknown consistency model '%s'!" % consistency_model)

  def _format_line(self, prefix, numerator, denominator):
    """Formats a line for output."""

    # Determine the output ratio.
    try:
      ratio = float(numerator) / denominator
    except ZeroDivisionError:
      ratio = float("nan")

    # Get the ratio as a string.
    ratio_string = "{0:.2%}".format(ratio)
    percent_spaces = 7 - len(ratio_string)

    # Work out how much the 'X of Y' needs padded to all be aligned. 47 is a
    # magic number, equivalent to the longest output line.
    spaces = (47 - len(prefix)) + percent_spaces
    spacer = " " * spaces

    # Determine how much to pad the numerator and denominator.
    numerator_padding = " " * (6 - len(str(int(numerator))))
    denominator_padding = " " * (6 - len(str(int(denominator))))

    return "{0}: {1}{2}({3}{4:.0f} of {5}{6:.0f})".format(prefix, ratio_string,
        spacer, numerator_padding, numerator, denominator_padding, denominator)

  def _test_consistency(self):
    """Tests that the simulation is consistent.

    The simulation is inconsistent if two processors have an illegal combination
    of states for a particular memory block (e.g. both caches have the memory
    block marked as 'MODIFIED'.

    Returns True if the simulation is consistent, False otherwise.

    This is VERY EXPENSIVE to compute!"""

    consistent = True
    for (cache1, cache2) in itertools.combinations(self.caches, 2):
      # Obtain the known slot ids. As the caches are backed by a dictionary,
      # not all slots may exist yet (or ever.)
      cache1_keyset = set(cache1.cache_lines)
      cache2_keyset = set(cache2.cache_lines)

      # Any slot that is in both dictionaries may contain the same memory block.
      for common_slot_id in cache1_keyset.intersection(cache2_keyset):
        cache1_slot = cache1.cache_lines[common_slot_id]
        cache2_slot = cache2.cache_lines[common_slot_id]

        if cache1_slot.tag != cache2_slot.tag:
          # The slots hold different memory blocks, so fine.
          continue

        states = (cache1_slot.state, cache2_slot.state)
        if states in SimulationEnvironment.INCONSISTENT_STATES:
          print("Iconsistent states found for slot %s, tag %s."
              "Cache %s: %s. Cache %s: %s." %
              (common_slot_id, cache1_slot.tag,
              cache1.cache_id, cache1_slot.state,
              cache2.cache_id, cache2_slot.state))
          consistent = False

    return consistent


def main():
  """Sets up and executes a simulation of a given trace file."""
  
  usage = ("Usage: %prog [options] consistency_model trace_file_name\n"
      "\nNote:\n\tAcceptable consistency models are 'SC' or 'TSO'.")
  parser = optparse.OptionParser(usage=usage)
  parser.add_option(
    "-p",
    "--number_processors",
    action="store",
    default=4,
    dest="number_processors",
    help="The number of processors (and thus caches.) [default: %default]",
    type="int")
  parser.add_option(
    "-l",
    "--number_cache_lines",
    action="store",
    default=128,
    dest="number_lines",
    help="The number of cache lines per cache. [default: %default]",
    type="int")
  parser.add_option(
    "-s",
    "--cache_line_size",
    action="store",
    default=4,
    dest="line_size",
    help="The size of each cache line. [default: %default]",
    type="int")
  parser.add_option(
    "-w",
    "--write_buffer_size",
    action="store",
    default=None,
    dest="write_buffer_size",
    help="The size of the write buffer. [default: 32]",
    type="int")
  parser.add_option(
    "-r",
    "--retire_at_count",
    action="store",
    default=None,
    dest="retire_at_count",
    help="The N for the retire-at-N policy. [default: 1]",
    type="int")
  parser.add_option(
    "-d",
    "--debug",
    action="store_true",
    default=False,
    dest="debug_mode",
    help="Turn debug mode on. [default: %default]")

  (options, args) = parser.parse_args()

  # The user must provide a consistency model and a trace file.
  if len(args) != 2:
    parser.print_help()
    return

  consistency_model = args[0].upper()
  if consistency_model not in ["SC", "TSO"]:
    print "ERROR: Unknown consistency model '%s'" % consistency_model
    return

  # Warn the user if they've set -w/-r but used SC.
  write_buffer_size = options.write_buffer_size
  retire_at_count = options.retire_at_count
  if (consistency_model == "SC" and
      (write_buffer_size is not None or retire_at_count is not None)):
    print("WARNING: Provided write buffer settings are being ignored due to "
        "SC consistency model!")

  trace_filename = args[1]
  if options.debug_mode:
    print "File: %s" % trace_filename

  simulation = SimulationEnvironment(
      options.number_processors,
      options.number_lines,
      options.line_size,
      consistency_model,
      debug_mode=options.debug_mode,
      write_buffer_size=write_buffer_size,
      retire_at_count=retire_at_count)
  simulation.simulate(trace_filename)
  simulation.report_stats()


if __name__ == "__main__":
  main()