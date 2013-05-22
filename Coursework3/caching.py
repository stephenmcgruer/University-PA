"""Contains classes and functions that simulate a basic processor cache."""


import collections


class SlotState(object):
  """An enumeration representing the possible states for a cache slot (line)."""

  INVALID, SHARED, MODIFIED = range(3)

  @classmethod
  def pretty_string(cls, state):
    """Return a human-readable version of an enum value."""

    if state == SlotState.INVALID:
      return "INVALID"
    elif state == SlotState.SHARED:
      return "SHARED"
    elif state == SlotState.MODIFIED:
      return "MODIFIED"
    elif state == None:
      return "None"
    else:
      raise ValueError("Unknown state %s!" % state)


class CacheSlot(object):
  """Represents a slot (line) in the cache.

  Does not store any data, only a tag and line state."""

  def __init__(self):
    self.tag = None
    self._state = SlotState.INVALID
    self._prev_state = None
    self.written_to = False

  @property
  def state(self):
    return self._state

  @state.setter
  def state(self, new_state):
    """Update the state of the cache slot."""

    self._prev_state = self._state
    self._state = new_state

  @property
  def previous_state(self):
    """The previous state of the cache slot."""

    return self._prev_state

  def __repr__(self):
    """The string representation of a cache slot."""

    return ("CacheSlot[state=%s, previous_state=%s, tag=%s, written_to=%s" %
        (SlotState.pretty_string(self._state),
        SlotState.pretty_string(self._prev_state),
        self.tag,
        self.written_to))


class Cache(object):
  """Represents a cache for a processor.

  A cache is defined by the number of lines in the cache, and the size of each
  line (given in number of words.)"""

  # Cycle costs for latency.
  _L1_CACHE_COST = 2
  _BUS_COST = 20
  _MAIN_MEMORY_COST = 200

  def __init__(self, cache_id, number_lines, line_size, bus, tracker,
      debug_mode):
    self.cache_id = cache_id

    if not _is_power_of_two(number_lines):
      raise ValueError("number_lines is not a power of 2!")

    if not _is_power_of_two(line_size):
      raise ValueError("line_size is not a power of 2!")

    self.slot_bits = _integer_log_base_two(number_lines)
    self.offset_bits = _integer_log_base_two(line_size)

    self.bus = bus
    self.bus.add_cache(self)

    self.tracker = tracker
    self.tracker.add_cache(self)

    # The cache contents are represented as a dictionary from slot id to
    # CacheSlots, which are dynamically created.
    self.cache_lines = collections.defaultdict(CacheSlot)

    # Track the cache latency.
    self.latency = 0

    self.debug_mode = debug_mode

  def write(self, address):
    """Handles a write to a memory address.

    Returns true if the write hit, false otherwise."""

    if self.debug_mode:
      print ("Cache %s: Write to %s" % (self.cache_id, address))

    write_latency, hit = self._process_write(address)

    # In SC, writes are on the critical path.
    self.latency += write_latency

    return hit

  def read(self, address):
    """Handles a read to a memory address.

    Returns true if the read hit, false otherwise."""

    read_latency, hit = self._process_read(address)
    self.latency += read_latency

    return hit

  def get_cache_line(self, slot_id):
    """Return a line in the cache.

    Used for gathering statistics."""

    return self.cache_lines[slot_id]

  def notify_read_miss(self, address):
    """Handles an external read-miss to an address.

    If the given address is cached locally, its state will be set to SHARED.

    Return True if the data would be returned by the cache, False if the cache
    didn't have the data."""

    tag, slot_id, _ = self._split_address(address)
    cache_slot = self.cache_lines[slot_id]

    if cache_slot.state == SlotState.MODIFIED and cache_slot.tag == tag:
      if self.debug_mode:
        print("Cache %s: Changing %s [tag=%s, slot_id=%s] from"
            " MODIFIED to SHARED." % (self.cache_id, address, tag, slot_id))

      # In a real processor, the memory line would be returned to the other
      # cache or written to main memory.

      # Update the cache slot.
      cache_slot.state = SlotState.SHARED

    # If the tag matches, and the cache slot either was already SHARED or is now
    # SHARED, the data could be returned from this cache.
    return cache_slot.tag == tag and cache_slot.state == SlotState.SHARED

  def notify_write_miss(self, address):
    """Handles an external write-miss to an address.

    If the given address is cached locally, its state will be set to INVALID."""

    tag, slot_id, _ = self._split_address(address)
    cache_slot = self.cache_lines[slot_id]

    if cache_slot.state != SlotState.INVALID and cache_slot.tag == tag:
      if self.debug_mode:
        print ("Cache %s: Changing %s [tag=%s, slot_id=%s] from"
            " MODIFIED/SHARED to INVALID." %
            (self.cache_id, address, tag, slot_id))

      # In a real processor, if we were in MODIFIED state, the memory line
      # would be returned to the other cache or written to main memory.

      # Update the cache slot.
      cache_slot.state = SlotState.INVALID

      # No need to update the tag or written_to status: INVALID overrides those.

  def notify_finished(self):
    """Notify the cache that the program is finished."""

    # No need to do anything for SC.
    pass

  def _process_write(self, address):
    """Processes a write to an address.

    Returns a tuple consisting of the write latency, and whether or not the
    write hit."""

    tag, slot_id, _ = self._split_address(address)
    cache_slot = self.cache_lines[slot_id]

    if self.debug_mode:
      print ("         [tag=%s, slot_id=%s]" % (tag, slot_id))

    # As the cache is write-through, the latency is simple - every write must
    # hit the cache, the bus, and main memory.
    write_latency = (Cache._L1_CACHE_COST + Cache._BUS_COST +
        Cache._MAIN_MEMORY_COST)

    hit = None

    # There are 4 important possibilities: the slot is INVALID (miss), another
    # memory line is in the slot (miss), the slot is SHARED (miss), or the
    # slot is MODIFIED (hit).
    if cache_slot.state == SlotState.INVALID:
      if self.debug_mode:
        prefix = " " * len("Cache %s: " % self.cache_id)
        print prefix + "Write miss (Slot is INVALID)."

      # If the slot is INVALID but the tag matches, some other processor caused
      # us to make this miss.
      coherence_miss = (tag == cache_slot.tag)
      if self.debug_mode and coherence_miss:
        print "Cache %s: Coherence miss." % self.cache_id

      # Inform the statistics tracker. This must be done BEFORE informing other
      # processors.
      self.tracker.write_miss(self.cache_id, address, tag, slot_id,
          coherence_miss)

      # Notify the bus.
      self.bus.write_miss(self.cache_id, address)

      # In a real cache, the memory line would be loaded from main memory or
      # other processors here.
      
      # Update the cache slot.
      cache_slot.state = SlotState.MODIFIED
      cache_slot.tag = tag
      # We're replacing another slot, but writing to it, so written_to should be True.
      cache_slot.written_to = True

      # We missed.
      hit = False

    elif cache_slot.tag != tag:
      if self.debug_mode:
        prefix = " " * len("Cache %s: " % self.cache_id)
        print prefix + "Write miss (Tag mismatch)."

      # Inform the statistics tracker. This must be done BEFORE informing other
      # processors.
      self.tracker.write_miss(self.cache_id, address, tag, slot_id, False)

      # Notify the bus.
      self.bus.write_miss(self.cache_id, address)

      # In a real cache, the memory line would be loaded from main memory or
      # other processors here.

      # Update the cache slot.
      cache_slot.state = SlotState.MODIFIED
      cache_slot.tag = tag
      # We're replacing another slot, but writing to it, so written_to should be True.
      cache_slot.written_to = True

      # We missed.
      hit = False

    elif cache_slot.state == SlotState.SHARED:
      if self.debug_mode:
        prefix = " " * len("Cache %s: " % self.cache_id)
        print prefix + "Write to SHARED."

      # If the previous state was MODIFIED and the tag matches, some other
      # processor caused us to make this miss.
      coherence_miss = (cache_slot.previous_state == SlotState.MODIFIED and
          tag == cache_slot.tag)

      if self.debug_mode and coherence_miss:
        print "Cache %s: Coherence miss." % self.cache_id

      # Inform the statistics tracker. This must be done BEFORE informing other
      # processors.
      self.tracker.write_miss(self.cache_id, address, tag, slot_id,
          coherence_miss)

      # A write to shared state still counts as a miss, so other processors
      # must be told.
      self.bus.write_miss(self.cache_id, address)

      # In a real cache, the memory line would *NOT* be loaded here, as there
      # is no need.

      # Update the cache slot.
      cache_slot.state = SlotState.MODIFIED
      cache_slot.tag = tag
      # The slot is now written to.
      cache_slot.written_to = True

      # We missed.
      hit = False

    elif cache_slot.state == SlotState.MODIFIED:
      if self.debug_mode:
        prefix = " " * len("Cache %s: " % self.cache_id)
        print prefix + "Local write hit."

      # Inform the statistics tracker.
      self.tracker.write_hit(self.cache_id, address, tag, slot_id)

      # There is no need to inform the bus as the line is in MODIFIED.

      # Update the cache slot anyway, so that the previous state is set
      # correctly. The only way to get to MODIFIED is to write, so no
      # need to set written_to.
      cache_slot.state = cache_slot.state

      # We hit!
      hit = True

    if hit is None:
      raise ValueError("cache_slot not in appropriate state!")

    return write_latency, hit

  def _process_read(self, address):
    """Processes a read instruction.

    Returns a tuple consisting of the read latency and whether it hit or not."""

    tag, slot_id, _ = self._split_address(address)
    cache_slot = self.cache_lines[slot_id]

    if self.debug_mode:
      print("Cache %s: Read from %s [tag=%s, slot_id=%s]" % (self.cache_id,
          address, tag, slot_id))

    # All reads access the L1 cache.
    read_latency = Cache._L1_CACHE_COST

    hit = None

    # There are 3 important possibilities: the slot is INVALID (miss), another
    # memory line is in the slot (miss), or the slot is either SHARED or
    # MODIFIED (hit).
    if cache_slot.state == SlotState.INVALID:
      if self.debug_mode:
        prefix = " " * len("Cache %s: " % self.cache_id)
        print prefix + "Read miss (Slot is INVALID)."

      # If the slot is INVALID but the tag matches, some other processor caused
      # us to make this miss.
      coherence_miss = (tag == cache_slot.tag)

      # Inform the statistics tracker. This must be done BEFORE informing other
      # processors.
      self.tracker.read_miss(self.cache_id, address, tag, slot_id,
          coherence_miss)

      # Bus latency: 20 cycles.
      read_latency += Cache._BUS_COST

      # Notify the bus.
      read_from_main_memory = self.bus.read_miss(self.cache_id, address)

      if read_from_main_memory:
        # Main memory latency: 200 cycles.
        read_latency += Cache._MAIN_MEMORY_COST

      # In a real cache, the memory line would be loaded from main memory or
      # other processors here.

      # Update the cache slot.
      cache_slot.state = SlotState.SHARED
      cache_slot.tag = tag
      # As we're replacing another slot, reset written_to.
      cache_slot.written_to = False

      # We missed.
      hit = False

    elif cache_slot.tag != tag:
      if self.debug_mode:
        prefix = " " * len("Cache %s: " % self.cache_id)
        print prefix + "Read miss (Tag mismatch)."

      # Inform the statistics tracker.
      self.tracker.read_miss(self.cache_id, address, tag, slot_id, False)

      # Bus latency: 20 cycles.
      read_latency += Cache._BUS_COST

      # Notify the bus.
      read_from_main_memory = self.bus.read_miss(self.cache_id, address)

      if read_from_main_memory:
        # Main memory latency: 200 cycles.
        read_latency += Cache._MAIN_MEMORY_COST

      # In a real cache, the memory line would be loaded from main memory or
      # other processors here.

      old_state = cache_slot.state
      # Update the cache slot.
      cache_slot.state = SlotState.SHARED
      cache_slot.tag = tag
      # As we're replacing another slot, reset written_to.
      cache_slot.written_to = False

      # We missed.
      hit = False

    elif (cache_slot.state == SlotState.SHARED or
        cache_slot.state == SlotState.MODIFIED):
      if self.debug_mode:
        prefix = " " * len("Cache %s: " % self.cache_id)
        print prefix + "Local read (SHARED or MODIFIED)."

      # Inform the statistics tracker.
      self.tracker.read_hit(self.cache_id, address, tag, slot_id)

      # There is no need to inform the bus as the line is in SHARED/MODIFIED.

      # Update the cache slot anyway, so that the previous state is set
      # correctly.
      cache_slot.state = cache_slot.state

      # We hit.
      hit = True

    if hit is None:
      raise ValueError("cache_slot not in appropriate state!")

    return read_latency, hit

  def _split_address(self, address):
    """Splits an address into the tag, slot, and offset."""

    if address < 0:
      raise ValueError("address must be non-negative!")

    # The offset is contained in the lowest 'self.offset_bits' bits.
    offset_mask = (1 << self.offset_bits) - 1
    offset = address & offset_mask

    # The slot id is contained in the middle 'self.slot_bits' bits.
    offset_and_slot_mask = (1 << (self.slot_bits + self.offset_bits)) - 1 
    slot = (address & offset_and_slot_mask) >> self.offset_bits

    # The tag is contained in the remaining bits above the offset and slot id.
    tag_mask = ~offset_and_slot_mask
    tag = (address & tag_mask) >> (self.slot_bits + self.offset_bits)

    return tag, slot, offset


class TSOCache(Cache):
  """Represents a Total Store Order (TSO) cache."""

  # Cost of snooping the write buffer.
  _WRITE_BUFFER_COST = 1

  def __init__(self, cache_id, number_lines, line_size, bus, tracker,
      write_buffer_size, retire_at_count, debug_mode):

    # Initialize parent class.
    super(TSOCache, self).__init__(cache_id, number_lines, line_size,
        bus, tracker, debug_mode)

    if write_buffer_size <= 0:
      raise ValueError("Write buffer size must be positive!")

    # Theoretically retire-at-0 is ok, but it's silly and equivalent to
    # retire-at-1 anyway, so may as well disallow it.
    if retire_at_count <= 0:
      raise ValueError("Retire-at count must be positive!")      

    self.write_buffer = []
    self.write_buffer_size = write_buffer_size
    self.retire_at_count = retire_at_count
    self.write_finishes_at = None

  def write(self, address):
    """Writes to a memory address.

    In a total store order cache, writes are buffered rather than immediately
    applied."""

    if self.debug_mode:
      print ("Cache %s: Write to %s" % (self.cache_id, address))

    self.tracker.write(self.cache_id, self.latency)

    # Drain write buffer if necessary.
    if len(self.write_buffer) == self.write_buffer_size:
      self._drain_write_buffer()

    self.write_buffer.append(address)

    # Check if writes should be retired (or if the write buffer should be
    # flushed.)
    self._check_write_buffer()

  def read(self, address):
    """Reads from a memory address.

    TSO reads are very similar to sequential consistency reads, except that they
    can snoop the write buffer, and must check if a write is ready to be issued
    after the read. (Reads are treated as atomic units so writes are only
    checked for after a read, not during.)

    Returns true if the write hit (in the cache or write buffer), false
    otherwise."""

    hit = None

    # Snoop the write buffer.
    self.latency += TSOCache._WRITE_BUFFER_COST

    if self.debug_mode:
      print ("Cache %s: Read; snooping write buffer (latency now %s)" % (
          self.cache_id, self.latency))

    if address in self.write_buffer:
      if self.debug_mode:
        print("Cache %s: Found address in write buffer." % self.cache_id)

      self.tracker.snoop_write_buffer(self.cache_id, address)

      hit = True
    else:
      # Address is not in write buffer; need to do a full read.
      read_latency, hit = self._process_read(address)

      self.latency += read_latency

      if self.debug_mode:
        print("Cache %s: Full read (latency now %s)" % (self.cache_id,
            self.latency))

    if self.debug_mode:
      print ("Cache %s: Read finished, checking write buffer (latency now %s, "
        "write finishes at %s)" % (self.cache_id, self.latency,
        self.write_finishes_at))

    # Check if a write should now be processed.
    self._check_write_buffer()

  def notify_finished(self):
    """Notify the cache that the program is finished."""

    # Process any remaining writes.
    self._drain_write_buffer()

  def _drain_write_buffer(self):
    """Drains the write buffer.
    
    These writes, and any write processing when the drain starts, are on the
    critical path and so will affect the latency count."""

    self.tracker.drain_write_buffer(self.cache_id, len(self.write_buffer))

    if self.debug_mode:
      print ("Cache %s: Draining write buffer (%s writes)." % (self.cache_id,
          len(self.write_buffer)))

    # First, check if there is a write currently processing.
    if self.write_finishes_at > self.latency:
      if self.debug_mode:
        print("Cache %s: Updating latency to %s" % (self.cache_id,
            self.write_finishes_at))

      self.latency = self.write_finishes_at
      self.write_finishes_at = None

    # Now drain the write buffer.
    while len(self.write_buffer) > 0:
      write_address = self.write_buffer.pop(0)
      write_latency, _ = self._process_write(write_address)

      # Critical path; update latency.
      self.latency += write_latency

      if self.debug_mode:
        print ("Cache %s: Processed write for drain (latency now %s)" % (
            self.cache_id, self.latency))

  def _check_write_buffer(self):
    """Checks the write buffer, processing writes if needed.

    Does not do draining of the write buffer."""

    write_still_processing = (self.write_finishes_at is not None and
        self.write_finishes_at > self.latency)

    if write_still_processing:
      if self.debug_mode:
        print ("Cache %s: Write still processing." % self.cache_id)

      # A write is ongoing, so nothing to do.
      return

    # Otherwise, the write is finished, so clear the tracking variable.
    self.write_finishes_at = None

    if self.debug_mode:
      print ("Cache %s: Possibility to retire write. Write buffer len: %s." % (
          self.cache_id, len(self.write_buffer)))

    if len(self.write_buffer) >= self.retire_at_count:
      # We can retire a write!

      write_address = self.write_buffer.pop(0)
      write_latency, _ = self._process_write(write_address)

      # These writes arent on the critical path, but we must keep track of when
      # they will finish.
      self.write_finishes_at = self.latency + write_latency

      if self.debug_mode:
        print ("Cache %s: Retiring write. Will finish in %s cycles (at %s)." % (self.cache_id,
            write_latency, self.write_finishes_at))


def _is_power_of_two(num):
  """Determines if a given number is a power of 2 or not."""

  return ((num & (num - 1)) == 0) and num > 0


def _integer_log_base_two(num):
  """Returns the integer log base two of a number.

  The given number must be a power of 2, or a ValueError will be raised."""

  if not _is_power_of_two(num):
    raise ValueError("Argument is not a power of 2!")

  answer = 0
  while 2**answer <= num:
    answer += 1

  return answer - 1
