"""The main driver to parse trace files and simulate their contents."""


import caching
import buses
import itertools
import optparse
import statistics


class SimulationEnvironment:
  """Represents a simulation of a set of caches and a bus.

  The simulation is able to parse a trace file and simulate its contents."""

  # The set of inconsistent cache line states for a given memory block across
  # two caches.
  INCONSISTENT_STATES = [
    (caching.SlotState.MODIFIED, caching.SlotState.MODIFIED),
    (caching.SlotState.MODIFIED, caching.SlotState.SHARED),
    (caching.SlotState.SHARED, caching.SlotState.MODIFIED)
  ]

  def __init__(self, number_processors, number_lines, line_size,
      debug_mode=False):
    """Initializes the simulation, setting up the bus and caches."""

    self.debug_mode = debug_mode

    self.tracker = statistics.SimulationStatisticsTracker()

    shared_bus = buses.Bus()

    # Set up the caches. Each cache will register itself with the bus.
    self.caches = []
    for cache_id in xrange(number_processors):
      cache = caching.Cache(cache_id, number_lines, line_size, shared_bus,
          self.tracker, self.debug_mode)
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

  def report_stats(self):
    """Prints out statistics on the simulation."""

    # The header.
    print "-" * 21
    print "Simulation Statistics"
    print "-" * 21
    print

    print "Per Cache Statistics:"
    print

    # Print the per-cache statistics (i.e. (a))
    for cache in self.caches:
      stats = self.tracker.get_cache_stats(cache.cache_id)

      accesses = stats["accesses"]
      reads = stats["reads"]
      writes = stats["writes"]

      misses = stats["misses"]
      read_misses = stats["read_misses"]
      write_misses = stats["write_misses"]
      coherence_misses = stats["coherence_misses"]

      dynamic_private_line_accesses = stats["dynamic_private_line_accesses"]
      dynamic_shared_read_only_line_accesses = stats["dynamic_shared_read_only_line_accesses"]
      dynamic_shared_read_write_line_accesses = (
          stats["dynamic_shared_read_write_line_accesses"])

      static_private_line_accesses = stats["static_private_line_accesses"]
      static_shared_read_only_line_accesses = stats["static_shared_read_only_line_accesses"]
      static_shared_read_write_line_accesses = (
          stats["static_shared_read_write_line_accesses"])

      print "Cache %s" % cache.cache_id

      print self._format_line("\tMiss rate", misses, accesses)
      print self._format_line("\tRead miss rate", read_misses, reads)
      print self._format_line("\tWrite miss rate", write_misses, writes)
      print self._format_line("\tCoherence miss rate", coherence_misses,
          misses)

      print self._format_line("\tDynamic private line access rate",
          dynamic_private_line_accesses, accesses)
      print self._format_line("\tDynamic shared read-only line access rate",
          dynamic_shared_read_only_line_accesses, accesses)
      print self._format_line("\tDynamic shared read-write line access rate",
          dynamic_shared_read_write_line_accesses, accesses)

      print self._format_line("\tStatic private line access rate",
          static_private_line_accesses, accesses)
      print self._format_line("\tStatic shared read-only line access rate",
          static_shared_read_only_line_accesses, accesses)
      print self._format_line("\tStatic shared read-write line access rate",
          static_shared_read_write_line_accesses, accesses)
      print

    # Print the general statistics.
    stats = self.tracker.get_general_stats()

    accesses = stats["accesses"]
    
    dynamic_private_line_accesses = stats["dynamic_private_line_accesses"]
    dynamic_shared_read_only_line_accesses = stats["dynamic_shared_read_only_line_accesses"]
    dynamic_shared_read_write_line_accesses = (
        stats["dynamic_shared_read_write_line_accesses"])
    
    static_private_line_accesses = stats["static_private_line_accesses"]
    static_shared_read_only_line_accesses = stats["static_shared_read_only_line_accesses"]
    static_shared_read_write_line_accesses = (
        stats["static_shared_read_write_line_accesses"])

    addressed_by_one_processor = stats["addressed_by_one_processor"]
    addressed_by_two_processors = stats["addressed_by_two_processors"]
    addressed_by_more_than_two_processors = (
        stats["addressed_by_more_than_two_processors"])
    addresses = stats["addresses"]

    print "General Statistics:"
    print

    print self._format_line("\tDynamic private line access rate",
        dynamic_private_line_accesses, accesses)
    print self._format_line("\tDynamic shared read-only line access rate",
        dynamic_shared_read_only_line_accesses, accesses)
    print self._format_line("\tDynamic shared read-write line access rate",
        dynamic_shared_read_write_line_accesses, accesses)

    print self._format_line("\tStatic private line access rate",
        static_private_line_accesses, accesses)
    print self._format_line("\tStatic shared read-only line access rate",
        static_shared_read_only_line_accesses, accesses)
    print self._format_line("\tStatic shared read-write line access rate",
        static_shared_read_write_line_accesses, accesses)

    print self._format_line("\tAddresses addressed by one processor",
        addressed_by_one_processor, addresses)
    print self._format_line("\tAddresses addressed by two processors",
        addressed_by_two_processors, addresses)
    print self._format_line("\tAddresses addressed by more than two processors",
        addressed_by_more_than_two_processors, addresses)

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
  
  usage = "Usage: %prog [options] trace_file_name"
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
    "-d",
    "--debug",
    action="store_true",
    default=False,
    dest="debug_mode",
    help="Turn debug mode on. [default: %default]")

  (options, args) = parser.parse_args()

  # The user must provide exactly one trace file.
  if len(args) != 1:
    parser.print_help()
    return

  trace_filename = args[0]
  if options.debug_mode:
    print "File: %s" % trace_filename

  simulation = SimulationEnvironment(options.number_processors,
      options.number_lines, options.line_size, debug_mode=options.debug_mode)
  simulation.simulate(trace_filename)
  simulation.report_stats()


if __name__ == "__main__":
  main()
