from caching import SlotState
import collections


class CacheStatistics:
  """Holds statistics for a particular cache."""

  def __init__(self, cache):
    self.cache = cache

    # Tracks the number of accesses to each memory line.
    # Indexed by the memory line, which is a (tag, slot_id) pair.
    self.access_counts = collections.defaultdict(int)

    # The set of individual addresses accessed by the cache.
    self.accessed_addresses = set()

    # The set of memory lines that the cache writes/reads to.
    self.written_lines = set()
    self.read_lines = set()

    self.read_hits = 0.0
    self.read_misses = 0.0

    self.write_hits = 0.0
    self.write_misses = 0.0

    # The misses caused by other caches invalidating a line.
    self.coherence_misses = 0.0

    # Dynamic cache line statistics.
    self.dynamic_private_accesses = 0.0
    self.dynamic_public_read_only_accesses = 0.0
    self.dynamic_public_read_write_accesses = 0.0

    # Static cache line statistics.
    self.static_private_accesses = None
    self.static_public_read_only_accesses = None
    self.static_public_read_write_accesses = None

    # Write buffer statistics.
    self.write_buffer_drains = 0
    self.total_writes_drained = 0
    self.write_buffer_snoops = 0

    # Used to track the latency between writes.
    self.last_write_latency = 0
    self.latencies_between_writes = []

  @property
  def accessed_lines(self):
    return self.written_lines.union(self.read_lines)

  @property
  def read_only_lines(self):
    return self.read_lines - self.written_lines

  @property
  def accesses(self):
    return self.hits + self.misses

  @property
  def reads(self):
    return self.read_hits + self.read_misses

  @property
  def writes(self):
    return self.write_hits + self.write_misses

  @property
  def hits(self):
    return self.read_hits + self.write_hits

  @property
  def misses(self):
    return self.read_misses + self.write_misses


class SimulationStatisticsTracker:
  """Tracks statistics for the entire simulation."""

  def __init__(self):
    self.caches = {}

  def add_cache(self, cache):
    """Register a cache with the tracker."""

    self.caches[cache.cache_id] = CacheStatistics(cache)

  def drain_write_buffer(self, cache_id, writes_drained):
    """Notify the tracker of a drain of the write buffer."""

    cache_stats = self.caches[cache_id]
    cache_stats.write_buffer_drains += 1
    cache_stats.total_writes_drained += writes_drained

  def snoop_write_buffer(self, cache_id, address):
    """Notify the tracker that the write buffer was snooped."""

    cache_stats = self.caches[cache_id]
    cache_stats.write_buffer_snoops += 1

  def write(self, cache_id, current_latency):
    """Notify the tracker of the delay between last write and this write."""

    cache_stats = self.caches[cache_id]

    latency_between_writes = current_latency - cache_stats.last_write_latency
    cache_stats.latencies_between_writes.append(latency_between_writes)
    cache_stats.last_write_latency = current_latency

  def read_hit(self, cache_id, address, tag, slot_id):
    """Notify the tracker of a read hit for a particular cache."""

    cache_stats = self.caches[cache_id]
    line = (tag, slot_id)

    cache_stats.read_hits += 1
    self._handle_read(cache_stats, address, line)

  def read_miss(self, cache_id, address, tag, slot_id, coherence_miss):
    """Notify the tracker of a read miss for a particular cache."""

    cache_stats = self.caches[cache_id]
    line = (tag, slot_id)

    cache_stats.read_misses += 1
    if coherence_miss:
      cache_stats.coherence_misses += 1
    self._handle_read(cache_stats, address, line)

  def write_hit(self, cache_id, address, tag, slot_id):
    """Notify the tracker of a write hit for a particular cache."""

    cache_stats = self.caches[cache_id]
    line = (tag, slot_id)

    cache_stats.write_hits += 1
    self._handle_write(cache_stats, address, line)

  def write_miss(self, cache_id, address, tag, slot_id, coherence_miss):
    """Notify the tracker of a write miss for a particular cache."""

    cache_stats = self.caches[cache_id]
    line = (tag, slot_id)

    cache_stats.write_misses += 1
    if coherence_miss:
      cache_stats.coherence_misses += 1
    self._handle_write(cache_stats, address, line)

  def get_cache_stats(self, cache_id):
    """Return a dictionary with statistics for a given cache."""

    cache_stats = self.caches[cache_id]

    # If necessary, compute the cache statistics.
    if cache_stats.static_private_accesses is None:
      self._compute_static_private_accesses(cache_id)
    if cache_stats.static_public_read_only_accesses is None:
      self._compute_static_public_read_only_accesses(cache_id)
    if cache_stats.static_public_read_write_accesses is None:
      self._compute_static_public_read_write_accesses(cache_id)

    # Fill up the dictionary.
    stats = {}
    stats["accesses"] = cache_stats.accesses
    stats["reads"] = cache_stats.reads
    stats["writes"] = cache_stats.writes

    stats["misses"] = cache_stats.misses
    stats["read_misses"] = cache_stats.read_misses
    stats["write_misses"] = cache_stats.write_misses
    stats["coherence_misses"] = cache_stats.coherence_misses

    stats["dynamic_private_line_accesses"] = cache_stats.dynamic_private_accesses
    stats["dynamic_shared_read_only_line_accesses"] = (
        cache_stats.dynamic_public_read_only_accesses)
    stats["dynamic_shared_read_write_line_accesses"] = (
        cache_stats.dynamic_public_read_write_accesses)

    stats["static_private_line_accesses"] = cache_stats.static_private_accesses
    stats["static_shared_read_only_line_accesses"] = (
        cache_stats.static_public_read_only_accesses)
    stats["static_shared_read_write_line_accesses"] = (
        cache_stats.static_public_read_write_accesses)

    return stats

  def get_general_stats(self):
    """Return a dictionary with statistics for the whole simulation."""

    # Check that each cache has had it's statistics calculated.
    for (cache_id, cache_stats) in self.caches.items():
      if cache_stats.static_private_accesses is None:
        self._compute_static_private_accesses(cache_id)
      if cache_stats.static_public_read_only_accesses is None:
        self._compute_static_public_read_only_accesses(cache_id)
      if cache_stats.static_public_read_write_accesses is None:
        self._compute_static_public_read_write_accesses(cache_id)

    # Compute the average private access count, public read-only count, and
    # public read-write count.

    caches_stats = self.caches.values()
    
    accesses = sum([cs.accesses for cs in caches_stats])
    dynamic_private_accesses = sum([cs.dynamic_private_accesses for cs in caches_stats])
    dynamic_public_read_only_accesses = sum(
      [cs.dynamic_public_read_only_accesses for cs in caches_stats])
    dynamic_public_read_write_accesses = sum(
      [cs.dynamic_public_read_write_accesses for cs in caches_stats])
    
    accesses = sum([cs.accesses for cs in caches_stats])
    static_private_accesses = sum([cs.static_private_accesses for cs in caches_stats])
    static_public_read_only_accesses = sum(
      [cs.static_public_read_only_accesses for cs in caches_stats])
    static_public_read_write_accesses = sum(
      [cs.static_public_read_write_accesses for cs in caches_stats])

    # Compute the addresses accessed by 1, 2, and >2 processes.
    all_accessed_addresses = set()
    for cache_stats in self.caches.values():
      all_accessed_addresses = all_accessed_addresses.union(
          cache_stats.accessed_addresses)
    number_addresses = float(len(all_accessed_addresses))

    # Count how many processors accessed each address.
    address_counts = collections.defaultdict(int)
    for address in all_accessed_addresses:
      for cache_stats in self.caches.values():
        if address in cache_stats.accessed_addresses:
          address_counts[address] += 1

    # Then filter to get each set.
    one_proc_addresses = filter(lambda x : address_counts[x] == 1,
        all_accessed_addresses)
    two_proc_addresses = filter(lambda x : address_counts[x] == 2,
        all_accessed_addresses)
    more_than_two_proc_addresses = filter(lambda x : address_counts[x] > 2,
        all_accessed_addresses)

    addressed_by_one_processor = len(one_proc_addresses)
    addressed_by_two_processors = len(two_proc_addresses)
    addressed_by_more_than_two_processors = len(more_than_two_proc_addresses)

    # Calculate the program latency.
    latencies = [cs.cache.latency for cs in caches_stats]
    max_latency = max(latencies)
    max_latency_cache = latencies.index(max_latency)

    # Write buffer statistics.
    cache_stats = caches_stats[max_latency_cache]
    write_buffer_drains = cache_stats.write_buffer_drains
    total_writes_drained = cache_stats.total_writes_drained
    try:
      average_writes_drained = float(total_writes_drained) / write_buffer_drains
    except ZeroDivisionError:
      average_writes_drained = float("nan")

    latencies_between_writes = cache_stats.latencies_between_writes
    try:
      mean_latency_between_writes = mean(latencies_between_writes)
      median_latency_between_writes = median(latencies_between_writes)
    except ZeroDivisionError:
      # No latency between writes recorded.
      mean_latency_between_writes = float("nan")
      median_latency_between_writes = float("nan")

    write_buffer_snoops = cache_stats.write_buffer_snoops

    # Fill up the dictionary.
    stats = {}
    stats["accesses"] = accesses

    stats["dynamic_private_line_accesses"] = dynamic_private_accesses
    stats["dynamic_shared_read_only_line_accesses"] = dynamic_public_read_only_accesses
    stats["dynamic_shared_read_write_line_accesses"] = dynamic_public_read_write_accesses

    stats["static_private_line_accesses"] = static_private_accesses
    stats["static_shared_read_only_line_accesses"] = static_public_read_only_accesses
    stats["static_shared_read_write_line_accesses"] = static_public_read_write_accesses

    stats["addressed_by_one_processor"] = addressed_by_one_processor
    stats["addressed_by_two_processors"] = addressed_by_two_processors
    stats["addressed_by_more_than_two_processors"] = (
        addressed_by_more_than_two_processors)
    stats["addresses"] = number_addresses

    stats["max_latency"] = max_latency
    stats["max_latency_cache"] = max_latency_cache
    stats["write_buffer_drains"] = write_buffer_drains
    stats["average_writes_drained"] = average_writes_drained
    stats["mean_latency_between_writes"] = mean_latency_between_writes
    stats["median_latency_between_writes"] = median_latency_between_writes
    stats["write_buffer_snoops"] = write_buffer_snoops


    return stats

  def _handle_read(self, cache_stats, address, line):
    """Handles statistics updates regarding a generic read."""

    cache_stats.read_lines.add(line)

    self._handle_access(cache_stats, address, line)

  def _handle_write(self, cache_stats, address, line):
    """Handles statistics updates regarding a generic write."""

    cache_stats.written_lines.add(line)

    self._handle_access(cache_stats, address, line)

  def _handle_access(self, cache_stats, address, line):
    """Handles statistics updates regarding a generic access."""

    cache_stats.accessed_addresses.add(address)
    cache_stats.access_counts[line] += 1

    issuing_cache_id = cache_stats.cache.cache_id

    (tag, slot) = line

    # Track dynamic access statistics.
    other_slots = []
    for other_cache_stats in self.caches.values():
      if other_cache_stats.cache.cache_id == issuing_cache_id:
        # Don't count self!
        continue

      other_cache_line = other_cache_stats.cache.get_cache_line(slot)
      if (other_cache_line.state != SlotState.INVALID and
          other_cache_line.tag == tag):
        other_slots.append(other_cache_line)

    # Determine the type of access: private, read-write, or read-only.
    if len(other_slots) == 0:
      cache_stats.dynamic_private_accesses += 1
    else:
      # Check whether any cache has written to the slot.
      remote_written = any(map(lambda x : x.written_to, other_slots))
      local_written = cache_stats.cache.get_cache_line(slot).written_to
      if remote_written or local_written:
        cache_stats.dynamic_public_read_write_accesses += 1
      else:
        cache_stats.dynamic_public_read_only_accesses += 1

  def _compute_static_private_accesses(self, cache_id):
    """Count the accesses to private lines for a cache."""

    cache_stats = self.caches[cache_id]

    # First, determine the lines that are private. These are defined as
    # all of the lines accessed by the given cache, excepting ones also
    # accessed by other caches.
    cache_lines = cache_stats.accessed_lines
    for (other_cache_id, other_cache_stats) in self.caches.iteritems():
      if cache_id == other_cache_id:
        # Dont count self!
        continue

      cache_lines = cache_lines - other_cache_stats.accessed_lines

    # Count the accesses to private lines.
    static_private_accesses = 0
    for line in cache_lines:
      static_private_accesses += cache_stats.access_counts[line]

    # Update the cache stats.
    cache_stats.static_private_accesses = static_private_accesses

  def _compute_static_public_read_only_accesses(self, cache_id):
    """Count the accesses to public, read-only lines for a cache."""

    cache_stats = self.caches[cache_id]

    # To compute shared read-only lines we must first determine what lines
    # are read-only by *any* other cache.    
    other_read_only_lines = set()
    for (other_cache_id, other_cache_stats) in self.caches.iteritems():
      if cache_id == other_cache_id:
        continue

      other_read_only_lines = other_read_only_lines.union(
          other_cache_stats.read_only_lines)

    # Then, intersect this cache's read-only lines with the global set,
    # to determine which lines this cache accessed.
    local_read_only_lines = cache_stats.read_only_lines
    shared_read_only_lines = local_read_only_lines.intersection(
        other_read_only_lines)

    # Finally, count the accesses to the public read-only lines.
    static_public_read_only_accesses = 0
    for line in shared_read_only_lines:
      static_public_read_only_accesses += cache_stats.access_counts[line]

    # Update the cache stats.
    cache_stats.static_public_read_only_accesses = static_public_read_only_accesses

  def _compute_static_public_read_write_accesses(self, cache_id):
    """Count the accesses to public, read-write lines for a cache."""

    # Grab this cache's stats.
    cache_stats = self.caches[cache_id]

    # To compute shared read-write lines we must first determine what lines
    # are accessed at all by any other cache. 
    other_accessed_lines = set()
    for (other_cache_id, other_cache_stats) in self.caches.iteritems():
      if cache_id == other_cache_id:
        continue

      other_accessed_lines = other_accessed_lines.union(
          other_cache_stats.accessed_lines)

    # Then determine which public lines are also accessed by this cache.
    shared_lines = cache_stats.accessed_lines.intersection(
        other_accessed_lines)

    # Count the accesses to public lines.
    static_public_read_write_accesses = 0
    for line in shared_lines:
      static_public_read_write_accesses += cache_stats.access_counts[line]

    # Skip accesses to read-only lines.
    static_public_read_write_accesses -= cache_stats.static_public_read_only_accesses

    # Update the cache stats.
    cache_stats.static_public_read_write_accesses = static_public_read_write_accesses


def mean(seq):
  """Calculate the mean of a sequence."""

  return float(sum(seq)) / len(seq)


def median(seq):
  """Calculate the median of a sequence."""

  sorted_seq = sorted(seq)
  length = len(sorted_seq)

  if len(sorted_seq) % 2 == 0:
    return (sorted_seq[length / 2] + sorted_seq[(length / 2) - 1]) / 2.0

  return sorted_seq[length / 2]