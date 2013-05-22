"""Tests for the caching module."""

import contextlib
from cStringIO import StringIO
import sys
import unittest

from caching import Cache, TSOCache, SlotState
from parse_trace import SimulationEnvironment


"""A context manager that allows us to capture print statements, i.e.

>> with capture_output() as out:
>>   print "Hello, World!"
>> out
['Hello, World!\n', '']
"""
@contextlib.contextmanager
def capture_output():
  old_out, old_err = sys.stdout, sys.stderr
  try:
    out = [StringIO(), StringIO()]
    sys.stdout, sys.stderr = out
    yield out
  finally:
    sys.stdout, sys.stdout = old_out, old_err
    out[0] = out[0].getvalue()
    out[1] = out[1].getvalue()


class FakeBus():
  """A fake implementation of the bus to be injected."""

  def add_cache(self, cache):
    pass

  def read_miss(self, cache_id, address):
    return False

  def write_miss(self, cache_id, address):
    return False


class FakeTracker():
  """A fake implementation of the tracker to be injected."""

  def add_cache(self, cache):
    pass

  def read_miss(self, cache_id, address, tag, slot_id, coherence_miss):
    pass

  def read_hit(self, cache_id, address, tag, slot_id):
    pass

  def write_miss(self, cache_id, address, tag, slot_id, coherence_miss):
    pass

  def write_hit(self, cache_id, address, tag, slot_id):
    pass

  def drain_write_buffer(self, cache_id, writes_drained):
    pass

  def write(self, cache_id, latency):
    pass

  def snoop_write_buffer(self, cache_id, address):
    pass


class CachingTest(unittest.TestCase):
  """Tests for the caching module."""

  # Default configuration. Individual tests may override.
  _NUMBER_OF_PROCESSORS = 4
  _NUMBER_OF_CACHE_LINES = 128
  _SIZE_OF_CACHE_LINE = 4

  def setUp(self):
    self.fake_bus = FakeBus()
    self.fake_tracker = FakeTracker()

    self.default_cache = Cache(
        0, # Cache id.
        CachingTest._NUMBER_OF_CACHE_LINES,
        CachingTest._SIZE_OF_CACHE_LINE,
        self.fake_bus,
        self.fake_tracker,
        debug_mode=False)

    # Simulations for the test_trace tests.
    self.sc_simulation = SimulationEnvironment(
      CachingTest._NUMBER_OF_PROCESSORS,
      CachingTest._NUMBER_OF_CACHE_LINES,
      CachingTest._SIZE_OF_CACHE_LINE,
      "SC",
      debug_mode=True, # Turn on to force consistency checks.
    )

    self.tso_simulation = SimulationEnvironment(
      CachingTest._NUMBER_OF_PROCESSORS,
      CachingTest._NUMBER_OF_CACHE_LINES,
      CachingTest._SIZE_OF_CACHE_LINE,
      "TSO",
      debug_mode=True, # Turn on to force consistency checks.
      write_buffer_size=32,
      retire_at_count=1)

  def test_initialization(self):
    """Tests that a Cache is initialized properly."""

    # First, the default cache. 128 lines maps to 7 slot bits, 4 words per line
    # maps to 2 offset bits.
    self.assertEqual(self.default_cache.cache_id, 0)
    self.assertEqual(self.default_cache.slot_bits, 7)
    self.assertEqual(self.default_cache.offset_bits, 2)
    self.assertEqual(self.default_cache.bus, self.fake_bus)
    self.assertEqual(self.default_cache.tracker, self.fake_tracker)

    # A different sized cache. 512 lines ==> 9 slot bits, 1 word per line ==> 0
    # offset bits.
    cache = Cache(1, 512, 1, self.fake_bus, self.fake_tracker, debug_mode=False)
    self.assertEqual(cache.cache_id, 1)
    self.assertEqual(cache.slot_bits, 9)
    self.assertEqual(cache.offset_bits, 0)

    # One more. 32 lines ==> 5 slot bits, 32 word per line ==> 5 offset bits.
    cache = Cache(2, 32, 32, self.fake_bus, self.fake_tracker, debug_mode=False)
    self.assertEqual(cache.cache_id, 2)
    self.assertEqual(cache.slot_bits, 5)
    self.assertEqual(cache.offset_bits, 5)

    # Finally, test the error-throwing cases: non-powers of two.

    with self.assertRaises(ValueError):
        Cache(2, 15, 32, self.fake_bus, self.fake_tracker, debug_mode=False)

    with self.assertRaises(ValueError):
        Cache(2, 32, 15, self.fake_bus, self.fake_tracker, debug_mode=False)

    with self.assertRaises(ValueError):
        Cache(2, -2, 32, self.fake_bus, self.fake_tracker, debug_mode=False)

    with self.assertRaises(ValueError):
        Cache(2, 32, -2, self.fake_bus, self.fake_tracker, debug_mode=False)

  def test_address_placement(self):
    """Tests that addresses are mapped to the correct slot.

    Note that this overlaps with testing actual MSI protocol, but that
    is not the aim here: only the actual breakdown of the address is
    of interest. The check for SHARED is only to make sure that the line
    is actually in the cache."""

    # First test the default setup: 128 lines, 4 words per line.

    # Address 5: slot 1, tag 0.
    self.default_cache.read(5)
    line = self.default_cache.get_cache_line(1)
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.tag, 0)

    # Address 522: slot 2, tag 1.
    self.default_cache.read(522)
    line = self.default_cache.get_cache_line(2)
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.tag, 1)

    # Address 523: still slot 2, tag 1.
    self.default_cache.read(523)
    line = self.default_cache.get_cache_line(2)
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.tag, 1)

    # Address 2571: also slot 2, but tag 5.
    self.default_cache.read(2571)
    line = self.default_cache.get_cache_line(2)
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.tag, 5)

    # Now test another cache: 16 lines, 8 words per line.
    cache = Cache(1, 16, 8, self.fake_bus, self.fake_tracker, debug_mode=False)

    # Address 5: slot 0, tag 0.
    cache.read(5)
    line = cache.get_cache_line(0)
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.tag, 0)

    # Address 522: slot 1, tag 4.
    cache.read(522)
    line = cache.get_cache_line(1)
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.tag, 4)

    # Address 527: still slot 1, tag 4.
    cache.read(527)
    line = cache.get_cache_line(1)
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.tag, 4)

    # Address 528: slot 2, still tag 4.
    cache.read(528)
    line = cache.get_cache_line(2)
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.tag, 4)

    # Address 2571: also slot 1, but tag 20.
    cache.read(2571)
    line = cache.get_cache_line(1)
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.tag, 20)

  def test_local_accesses(self):
    """Tests that local accesses adhere to the MSI protocol."""

    # State transitions should be:
    #   INVALID + read ==> read_miss + SHARED.
    #   INVALID + write ==> write_miss + MODIFIED.
    #   SHARED + read ==> read_hit + SHARED.
    #   SHARED + write ==> write_miss + MODIFIED.
    #   MODIFIED + read ==> read_hit + MODIFIED.
    #   MODIFIED + write ==> write_hit + MODIFIED.

    # INVALID + read.
    hit = self.default_cache.read(10)
    self.assertFalse(hit)
    line = self.default_cache.get_cache_line(2) # Address 10 ==> slot 2.
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertFalse(line.written_to)

    # INVALID + write.
    hit = self.default_cache.write(20)
    self.assertFalse(hit)
    line = self.default_cache.get_cache_line(5) # Address 20 ==> slot 5.
    self.assertEqual(line.state, SlotState.MODIFIED)
    self.assertTrue(line.written_to)

    # SHARED + read.
    self.default_cache.read(30) # Prime the cache.
    hit = self.default_cache.read(31)
    self.assertTrue(hit)
    line = self.default_cache.get_cache_line(7) # Address 31 ==> slot 7.
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertFalse(line.written_to)

    # SHARED + write.
    self.default_cache.read(40) # Prime the cache.
    hit = self.default_cache.write(41)
    self.assertFalse(hit)
    line = self.default_cache.get_cache_line(10) # Address 41 ==> slot 10.
    self.assertEqual(line.state, SlotState.MODIFIED)
    self.assertTrue(line.written_to)

    # MODIFIED + read
    self.default_cache.write(50) # Prime the cache.
    hit = self.default_cache.read(51)
    self.assertTrue(hit)
    line = self.default_cache.get_cache_line(12) # Address 51 ==> slot 12.
    self.assertEqual(line.state, SlotState.MODIFIED)
    self.assertTrue(line.written_to)

    # MODIFIED + write
    self.default_cache.write(60) # Prime the cache.
    hit = self.default_cache.write(61)
    self.assertTrue(hit)
    line = self.default_cache.get_cache_line(15) # Address 61 ==> slot 15.
    self.assertEqual(line.state, SlotState.MODIFIED)
    self.assertTrue(line.written_to)

    # Mismatching tags in any non-INVALID state should be equivalent to INVALID.

    # SHARED + read.
    self.default_cache.read(30) # Prime the cache.
    hit = self.default_cache.read(2590) # Access a different tag.
    self.assertFalse(hit)
    line = self.default_cache.get_cache_line(7) # Address 30|2590 ==> slot 7.
    self.assertFalse(line.written_to)

    # SHARED + write.
    self.default_cache.read(40) # Prime the cache.
    hit = self.default_cache.write(10280) # Access a different tag.
    self.assertFalse(hit)
    line = self.default_cache.get_cache_line(10) # Address 40|10280 ==> slot 10.
    self.assertTrue(line.written_to)

    # MODIFIED + read
    self.default_cache.write(50) # Prime the cache.
    hit = self.default_cache.read(5682) # Access a different tag.
    self.assertFalse(hit)
    line = self.default_cache.get_cache_line(12) # Address 50|5682 ==> slot 12.
    self.assertFalse(line.written_to) # 5682 has only been read.

    # MODIFIED + write
    self.default_cache.write(60) # Prime the cache.
    hit = self.default_cache.write(1596) # Access a different tag.
    self.assertFalse(hit)
    line = self.default_cache.get_cache_line(15) # Address 60|1596 ==> slot 12.
    self.assertTrue(line.written_to)

  def test_remote_accesses(self):
    """Tests that remote accesses adhere to the MSI protocol."""

    # State transitions should be:
    #   INVALID + remote read miss ==> INVALID.
    #   INVALID + remote write miss ==> INVALID.
    #   SHARED + remote read miss ==> SHARED.
    #   SHARED + remote write miss ==> INVALID.
    #   MODIFIED + remote read miss ==> SHARED.
    #   MODIFIED + remote write miss ==> INVALID.

    # INVALID + remote read miss.
    self.default_cache.notify_read_miss(10)
    line = self.default_cache.get_cache_line(2) # Address 10 ==> slot 2.
    self.assertEqual(line.state, SlotState.INVALID)
    self.assertEqual(line.previous_state, None)

    # INVALID + remote write miss.
    self.default_cache.notify_write_miss(20)
    line = self.default_cache.get_cache_line(5) # Address 20 ==> slot 5.
    self.assertEqual(line.state, SlotState.INVALID)
    self.assertEqual(line.previous_state, None)

    # SHARED + remote read miss.
    self.default_cache.read(30) # Prime the cache.
    self.default_cache.notify_read_miss(31)
    line = self.default_cache.get_cache_line(7) # Address 31 ==> slot 7.
    self.assertEqual(line.state, SlotState.SHARED)
    # The previous_state variable tracks the previous state for coherence-caused
    # changes, so won't have changed here.
    self.assertEqual(line.previous_state, SlotState.INVALID)

    # SHARED + remote write miss.
    self.default_cache.read(40) # Prime the cache.
    self.default_cache.notify_write_miss(41)
    line = self.default_cache.get_cache_line(10) # Address 41 ==> slot 10.
    self.assertEqual(line.state, SlotState.INVALID)
    self.assertEqual(line.previous_state, SlotState.SHARED)

    # MODIFIED + remote read miss.
    self.default_cache.write(50) # Prime the cache.
    self.default_cache.notify_read_miss(51)
    line = self.default_cache.get_cache_line(12) # Address 51 ==> slot 12.
    self.assertEqual(line.state, SlotState.SHARED)
    self.assertEqual(line.previous_state, SlotState.MODIFIED)

    # MODIFIED + remote write miss.
    self.default_cache.write(60) # Prime the cache.
    self.default_cache.notify_write_miss(61)
    line = self.default_cache.get_cache_line(15) # Address 61 ==> slot 15.
    self.assertEqual(line.state, SlotState.INVALID)
    self.assertEqual(line.previous_state, SlotState.MODIFIED)

    # Mismatching tags should not cause a change.

    # SHARED + write: shouldn't go to INVALID.
    self.default_cache.read(30) # Prime the cache.
    self.default_cache.notify_write_miss(2590) # Write miss for different tag.
    line = self.default_cache.get_cache_line(7) # Address 30|2590 ==> slot 7.
    self.assertEqual(line.state, SlotState.SHARED)

    # MODIFIED + read: shouldn't go to SHARED.
    self.default_cache.write(40) # Prime the cache.
    self.default_cache.notify_read_miss(10280) # Read miss for different tag.
    line = self.default_cache.get_cache_line(10) # Address 40|10280 ==> slot 10.
    self.assertEqual(line.state, SlotState.MODIFIED)

  def test_write_tracking(self):
    """Tests that writes to a cache line are correctly tracked."""

    # Basic case: line not written to.
    self.default_cache.read(10)
    self.default_cache.read(11)
    line = self.default_cache.get_cache_line(2) # Address 10 ==> slot 2.
    self.assertFalse(line.written_to)

    # Basic case: line written to.
    self.default_cache.read(20)
    self.default_cache.write(21)
    self.default_cache.read(21)
    line = self.default_cache.get_cache_line(5) # Address 20 ==> slot 5.
    self.assertTrue(line.written_to)

    # Basic case: line written to, then flushed.
    self.default_cache.read(30)
    self.default_cache.write(31)
    self.default_cache.read(543) # Cache slot flushed.
    line = self.default_cache.get_cache_line(7) # Address 30|543 ==> slot 7.
    self.assertFalse(line.written_to)

    # Basic case: line written to, then flushed, then re-filled.
    self.default_cache.read(40)
    self.default_cache.write(41)
    self.default_cache.read(553) # Cache slot flushed.
    self.default_cache.read(40) # Re-filled.
    line = self.default_cache.get_cache_line(10) # Address 50|553 ==> slot 10.
    self.assertFalse(line.written_to)

    # More complex case. Line written to, then flushed by external processor.
    self.default_cache.write(50)
    self.default_cache.notify_write_miss(51) # Flush.
    line = self.default_cache.get_cache_line(12) # Address 50 ==> slot 12
    self.assertTrue(line.written_to)

    # More complex case. Line written to, then set to SHARED by external processor.
    self.default_cache.write(60)
    self.default_cache.notify_read_miss(61) # Set to SHARED.
    line = self.default_cache.get_cache_line(15) # Address 60 ==> slot 15
    self.assertTrue(line.written_to)

  def test_sc_read_latency(self):
    """Tests the measurements of read-latency in an SC cache."""

    # Cache with 16 lines, 8 words/line.
    cache = Cache(1, 16, 8, self.fake_bus, self.fake_tracker, False)

    # Test object in cache.
    cache.read(1) # Prime cache.
    cache.latency = 0
    cache.read(1)
    self.assertEqual(cache.latency, 2)

    cache.latency = 0

    # Test line returned by other processor.
    cache.read(9)
    self.assertEqual(cache.latency, 22)

    cache.latency = 0

    # Test line returned by main memory.

    # Duck-punch the fake bus to claim that it read from memory.
    # (Don't you love Python? Such abuse! :D)
    old_read_miss = FakeBus.read_miss
    def new_read_miss(self, cache_id, address):
        return True
    FakeBus.read_miss = new_read_miss 

    cache.read(18)
    self.assertEqual(cache.latency, 222)

    FakeBus.read_miss = old_read_miss

  def test_tso_read_latency(self):
    """Tests the measurements of read-latency in a TSO cache."""

    # Cache with 16 lines, 8 words/line, 4-write buffer with retire-at-2.
    cache = TSOCache(1, 16, 8, self.fake_bus, self.fake_tracker, 4, 2, False)

    # First test that write buffers are snooped correctly.
    cache.write(5)
    cache.read(5)
    self.assertEqual(cache.latency, 1)

    cache.latency = 0

    # Test value that is in the L1 cache.
    cache.read(4) # Prime the cache.
    cache.latency = 0
    cache.read(4)
    self.assertEqual(cache.latency, 3)

    cache.latency = 0

    # Test value returned by other processor.
    cache.read(19)
    self.assertEqual(cache.latency, 23)

    cache.latency = 0

    # Test value returned by main memory.

    # Duck-punch the fake bus to claim that it read from memory.
    # (Don't you love Python? Such abuse! :D)
    old_read_miss = FakeBus.read_miss
    def new_read_miss(self, cache_id, address):
        return True
    FakeBus.read_miss = new_read_miss 

    cache.read(26)
    self.assertEqual(cache.latency, 223)

    # Restore the FakeBus class.
    FakeBus.read_miss = old_read_miss

  def test_sc_write_latency(self):
    """Tests the measurements of write-latency in an SC cache.

    All writes in SC take 222 cycles, due to write-through cache."""

    # Cache with 16 lines, 8 words/line.
    cache = Cache(1, 16, 8, self.fake_bus, self.fake_tracker, False)

    # Test writing to something in cache.
    cache.write(5) # Prime cache.
    cache.latency = 0
    cache.write(5)
    self.assertEqual(cache.latency, 222)

    cache.latency = 0

    # Test writing to something that another processor can return.
    cache.write(9)
    self.assertEqual(cache.latency, 222)

    cache.latency = 0

    # Test value returned by main memory.

    # Duck-punch the fake bus to claim that it read from memory.
    # (Don't you love Python? Such abuse! :D)
    old_read_miss = FakeBus.read_miss
    def new_read_miss(self, cache_id, address):
        return True
    FakeBus.read_miss = new_read_miss 

    cache.write(20)
    self.assertEqual(cache.latency, 222)

    # Restore the FakeBus class.
    FakeBus.read_miss = old_read_miss

  def test_tso_write_latency(self):
    """Tests the measurements of write-latency in a TSO cache.

    Write latency is complicated in TSO: writes normally do not add to the cache
    latency, unless they are involved in a write buffer drain. Additionally, any
    write executing when a write buffer drain happens contributes the remainder
    of its cycles to the latency."""

    # Cache with 16 lines, 8 words/line, 4-write buffer with retire-at-2.
    cache = TSOCache(1, 16, 8, self.fake_bus, self.fake_tracker, 4, 2, False)

    # Single write: should be buffered.
    cache.write(5)
    self.assertEqual(cache.latency, 0)

    # A second write: should trip retire at N, but no effect on latency.
    cache.write(10)
    self.assertEqual(cache.latency, 0)
    self.assertEqual(len(cache.write_buffer), 1)

    # Force a drain.
    cache.write(15) # 2 writes in buffer
    cache.write(20) # 3 writes in buffer
    cache.write(25) # 4 writes in buffer; buffer should be full.
    cache.write(30) # Should force a drain.
    # Latency will be 4 writes in buffer, plus the one that was processing.
    self.assertEqual(cache.latency, 222*5)
    self.assertEqual(len(cache.write_buffer), 1)

  def test_tso_check_write_buffer(self):
    """Tests that the check-buffer logic in the TSO cache is correct."""

    # Cache with 16 lines, 8 words/line, 4-write buffer with retire-at-2.
    cache = TSOCache(1, 16, 8, self.fake_bus, self.fake_tracker, 4, 2, False)

    # First, check that the method does nothing if a write is still processing.
    cache.write_finishes_at = 15 # Fake a write in progress.
    cache.write_buffer = [10, 5, 20] # Fake some writes.
    cache._check_write_buffer()
    self.assertEqual(cache.write_finishes_at, 15)
    self.assertEqual(cache.latency, 0)
    self.assertEqual(cache.write_buffer, [10, 5, 20])

    # Check that if a write is not in process but there are less than N (here,
    # 2) writes in the buffer, it still does nothing.
    cache.write_finishes_at = None
    cache.write_buffer = [10]
    cache._check_write_buffer()
    self.assertEqual(cache.write_finishes_at, None)
    self.assertEqual(cache.latency, 0)
    self.assertEqual(cache.write_buffer, [10])

    # Check that if a write is finished and there are less than N (here, 2)
    # writes in the buffer, the write is cleared but thats it.
    cache.write_finishes_at = 10
    cache.latency = 15
    cache.write_buffer = [10]
    cache._check_write_buffer()
    self.assertEqual(cache.write_finishes_at, None)
    self.assertEqual(cache.latency, 15)
    self.assertEqual(cache.write_buffer, [10])

    # Check that if a write is finished and there are N writes in the buffer,
    # another write is retired, from the correct end of the line.
    cache.write_finishes_at = 10
    cache.latency = 15
    cache.write_buffer = [10, 5]
    cache._check_write_buffer()
    self.assertEqual(cache.write_finishes_at, 237)
    self.assertEqual(cache.latency, 15)
    self.assertEqual(cache.write_buffer, [5])

    # Check that if a write is not in progress and there are N writes in the
    # buffer, another write is retired, from the correct end of the line.
    cache.write_finishes_at = None
    cache.latency = 25
    cache.write_buffer = [5, 10]
    cache._check_write_buffer()
    self.assertEqual(cache.write_finishes_at, 247)
    self.assertEqual(cache.latency, 25)
    self.assertEqual(cache.write_buffer, [10])

  def test_tso_drain_buffer(self):
    """Tests that the drain buffer logic in the TSO cache is correct."""

    # Cache with 16 lines, 8 words/line, 4-write buffer with retire-at-2.
    cache = TSOCache(1, 16, 8, self.fake_bus, self.fake_tracker, 4, 2, False)

    # Check that draining a cache always clears it completely.
    cache.write_buffer = [1]
    cache._drain_write_buffer()
    self.assertEqual(cache.write_buffer, [])

    cache.write_buffer = [1, 2]
    cache._drain_write_buffer()
    self.assertEqual(cache.write_buffer, [])

    cache.write_buffer = [3, 4, 5, 6, 7]
    cache._drain_write_buffer()
    self.assertEqual(cache.write_buffer, [])

    cache.write_buffer = []
    cache._drain_write_buffer()
    self.assertEqual(cache.write_buffer, [])

    # Check that when the buffer is drained, any ongoing writes are counted as latency.
    cache.write_buffer = []
    cache.latency = 20
    cache.write_finishes_at = 126
    cache._drain_write_buffer()
    self.assertEqual(cache.latency, 126)
    self.assertEqual(cache.write_finishes_at, None)

    cache.write_buffer = [10, 20]
    cache.latency = 20
    cache.write_finishes_at = 126
    cache._drain_write_buffer()
    self.assertEqual(cache.latency, 126 + (2 * 222))
    self.assertEqual(cache.write_finishes_at, None)

    # Check that when the buffer is drained, all writes are counted.
    cache.write_buffer = [10, 20, 30, 40]
    cache.latency = 0
    cache.write_finishes_at = None
    cache._drain_write_buffer()
    self.assertEqual(cache.latency, 4 * 222)
    self.assertEqual(cache.write_finishes_at, None)

    # Check that when drained, writes execute in the correct order.
    cache.write_buffer = [10, 138] # Same slot (1), different tag (0 and 1).
    cache.latency = 0
    cache.write_finishes_at = None
    cache._drain_write_buffer()
    self.assertEqual(cache.latency, 2 * 222)
    self.assertEqual(cache.get_cache_line(1).tag, 1)
    self.assertEqual(cache.get_cache_line(1).state, SlotState.MODIFIED)

  def test_tso_post_program_drain(self):
    """Test the post-program drain of the write buffer."""

    # Cache with 16 lines, 8 words/line, 4-write buffer with retire-at-2.
    cache = TSOCache(1, 16, 8, self.fake_bus, self.fake_tracker, 4, 2, False)

    # Test that nothing changes if theres nothing in the write buffer.
    cache.latency = 500
    cache.notify_finished()
    self.assertEqual(cache.latency, 500)
    self.assertEqual(cache.write_buffer, [])
    self.assertEqual(cache.write_finishes_at, None)

    # Test that the write buffer is properly cleared if there is something in it.
    cache.latency = 500
    cache.write_buffer = [10, 20]
    cache.write_finishes_at = 505
    cache.notify_finished()
    self.assertEqual(cache.latency, 505 + (2 * 222))
    self.assertEqual(cache.write_buffer, [])
    self.assertEqual(cache.write_finishes_at, None)

  def test_sc_read_latency_from_trace(self):
    """Tests that SC read latency is correctly calculated from a trace.

    Basically worse than the unittests, but apparently we must provide test
    traces..."""

    with capture_output():
      self.sc_simulation.simulate("test_traces/sc_read_trace.out")

    # Get the statistics.
    stats = self.sc_simulation.tracker.get_general_stats()

    self.assertEqual(stats["max_latency"], 246)
    self.assertEqual(stats["max_latency_cache"], 0)

  def test_sc_write_latency_from_trace(self):
    """Tests that SC write latency is correctly calculated from a trace.

    Basically worse than the unittests, but apparently we must provide test
    traces..."""

    with capture_output():
      self.sc_simulation.simulate("test_traces/sc_write_trace.out")

    # Get the statistics.
    stats = self.sc_simulation.tracker.get_general_stats()

    self.assertEqual(stats["max_latency"], 666)
    self.assertEqual(stats["max_latency_cache"], 0)

  def test_tso_read_latency_from_trace(self):
    """Tests that TSO read latency is correctly calculated from a trace.

    Basically worse than the unittests, but apparently we must provide test
    traces..."""

    with capture_output():
      self.tso_simulation.simulate("test_traces/tso_read_trace.out")

    # Get the statistics.
    stats = self.tso_simulation.tracker.get_general_stats()

    self.assertEqual(stats["max_latency"], 693)
    self.assertEqual(stats["max_latency_cache"], 0)

  def test_tso_write_latency_from_trace(self):
    """Tests that TSO write latency is correctly calculated from a trace.

    Basically worse than the unittests, but apparently we must provide test
    traces..."""

    with capture_output():
      self.tso_simulation.simulate("test_traces/tso_write_trace.out")

    # Get the statistics.
    stats = self.tso_simulation.tracker.get_general_stats()

    self.assertEqual(stats["max_latency"], 889)
    self.assertEqual(stats["max_latency_cache"], 0)

if __name__ == "__main__":
  unittest.main()