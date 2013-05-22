"""Tests for the caching module."""

import unittest

from buses import Bus
from caching import Cache
from statistics import SimulationStatisticsTracker


class StatisticsTest(unittest.TestCase):
  """Tests for the statistics module."""

  # Default configuration for caches.
  _NUMBER_OF_CACHE_LINES = 128
  _SIZE_OF_CACHE_LINE = 4

  def setUp(self):
    self.tracker = SimulationStatisticsTracker()
    self.bus = Bus()

    self.caches = []
    for i in range(4):
        cache = Cache(
            i, # Cache id
            StatisticsTest._NUMBER_OF_CACHE_LINES,
            StatisticsTest._SIZE_OF_CACHE_LINE,
            self.bus,
            self.tracker,
            debug_mode=False)
        self.caches.append(cache)

  def test_initialization(self):
    """Test that a SimulationStatisticsTracker is initialized properly."""

    # setUp() adds 4 caches.
    self.assertEqual(len(self.tracker.caches), 4)

  def test_basic_miss_tracking(self):
    """Test the basic miss tracking, without coherence influences."""

    # First test the basic MSI protocol, using P0.
    #   INVALID + read ==> read_miss + SHARED.
    #   INVALID + write ==> write_miss + MODIFIED.
    #   SHARED + read ==> read_hit + SHARED.
    #   SHARED + write ==> write_miss + MODIFIED.
    #   MODIFIED + read ==> read_hit + MODIFIED.
    #   MODIFIED + write ==> write_hit + MODIFIED.

    cache = self.caches[0]
    cache_stats = self.tracker.caches[0]

    # Initial test.
    self.assertEqual(cache_stats.hits, 0)
    self.assertEqual(cache_stats.read_hits, 0)
    self.assertEqual(cache_stats.write_hits, 0)
    self.assertEqual(cache_stats.misses, 0)
    self.assertEqual(cache_stats.read_misses, 0)
    self.assertEqual(cache_stats.write_misses, 0)

    cache.read(0) # Read miss to INVALID.
    self.assertEqual(cache_stats.hits, 0)
    self.assertEqual(cache_stats.read_hits, 0)
    self.assertEqual(cache_stats.write_hits, 0)
    self.assertEqual(cache_stats.misses, 1)
    self.assertEqual(cache_stats.read_misses, 1)
    self.assertEqual(cache_stats.write_misses, 0)

    cache.write(4) # Write miss to INVALID.
    self.assertEqual(cache_stats.hits, 0)
    self.assertEqual(cache_stats.read_hits, 0)
    self.assertEqual(cache_stats.write_hits, 0)
    self.assertEqual(cache_stats.misses, 2)
    self.assertEqual(cache_stats.read_misses, 1)
    self.assertEqual(cache_stats.write_misses, 1)

    cache.read(1) # Read hit to SHARED.
    self.assertEqual(cache_stats.hits, 1)
    self.assertEqual(cache_stats.read_hits, 1)
    self.assertEqual(cache_stats.write_hits, 0)
    self.assertEqual(cache_stats.misses, 2)
    self.assertEqual(cache_stats.read_misses, 1)
    self.assertEqual(cache_stats.write_misses, 1)

    cache.write(2) # Write miss to SHARED.
    self.assertEqual(cache_stats.hits, 1)
    self.assertEqual(cache_stats.read_hits, 1)
    self.assertEqual(cache_stats.write_hits, 0)
    self.assertEqual(cache_stats.misses, 3)
    self.assertEqual(cache_stats.read_misses, 1)
    self.assertEqual(cache_stats.write_misses, 2)

    cache.read(0) # Read hit to MODIFIED.
    self.assertEqual(cache_stats.hits, 2)
    self.assertEqual(cache_stats.read_hits, 2)
    self.assertEqual(cache_stats.write_hits, 0)
    self.assertEqual(cache_stats.misses, 3)
    self.assertEqual(cache_stats.read_misses, 1)
    self.assertEqual(cache_stats.write_misses, 2)

    cache.write(0) # Write hit to MODIFIED.
    self.assertEqual(cache_stats.hits, 3)
    self.assertEqual(cache_stats.read_hits, 2)
    self.assertEqual(cache_stats.write_hits, 1)
    self.assertEqual(cache_stats.misses, 3)
    self.assertEqual(cache_stats.read_misses, 1)
    self.assertEqual(cache_stats.write_misses, 2)

    # Now test a set of basic instructions, using P1.

    cache = self.caches[1]
    cache_stats = self.tracker.caches[1]

    cache.read(5)    # Read miss.
    cache.write(10)  # Write miss.
    cache.read(11)   # Read hit.
    cache.read(6)    # Read hit.
    cache.read(20)   # Read miss.
    cache.write(11)  # Write hit.
    cache.write(7)   # Write miss.
    cache.read(5)    # Read hit.
    cache.read(24)   # Read miss.
    cache.write(35)  # Write miss.
    cache.write(24)  # Write miss.
    cache.read(2053) # Read miss.
    cache.read(5)    # Read miss.

    self.assertEqual(cache_stats.hits, 4)
    self.assertEqual(cache_stats.read_hits, 3)
    self.assertEqual(cache_stats.write_hits, 1)
    self.assertEqual(cache_stats.misses, 9)
    self.assertEqual(cache_stats.read_misses, 5)
    self.assertEqual(cache_stats.write_misses, 4)

  def test_coherence_influenced_miss_tracking(self):
    """Test miss tracking, with coherence influences.

    These tests are not fully complete, but should cover many cases."""

    # First test the basic remote MSI protocol, using P0 and P1.
    #   INVALID + remote read miss ==> INVALID.
    #   INVALID + remote write miss ==> INVALID.
    #   SHARED + remote read miss ==> SHARED.
    #   SHARED + remote write miss ==> INVALID.
    #   MODIFIED + remote read miss ==> SHARED.
    #   MODIFIED + remote write miss ==> INVALID.

    cache0 = self.caches[0]
    cache1 = self.caches[1]
    cache_stats = self.tracker.caches[0]

    cache1.read(1) # Remote read miss to INVALID line. 
    self.assertEqual(cache_stats.hits, 0)
    self.assertEqual(cache_stats.read_hits, 0)
    self.assertEqual(cache_stats.write_hits, 0)
    self.assertEqual(cache_stats.misses, 0)
    self.assertEqual(cache_stats.read_misses, 0)
    self.assertEqual(cache_stats.write_misses, 0)
    self.assertEqual(cache_stats.coherence_misses, 0)

    cache1.write(1) # Remote write miss to INVALID line. 
    self.assertEqual(cache_stats.hits, 0)
    self.assertEqual(cache_stats.read_hits, 0)
    self.assertEqual(cache_stats.write_hits, 0)
    self.assertEqual(cache_stats.misses, 0)
    self.assertEqual(cache_stats.read_misses, 0)
    self.assertEqual(cache_stats.write_misses, 0)
    self.assertEqual(cache_stats.coherence_misses, 0)

    # SHARED + remote read miss.
    cache0.read(4) # Prime cache to SHARED.
    cache1.read(5) # Remote read miss to the SHARED line.
    cache0.read(4) # Should still be SHARED so hit.
    self.assertEqual(cache_stats.hits, 1)
    self.assertEqual(cache_stats.read_hits, 1)
    self.assertEqual(cache_stats.write_hits, 0)
    self.assertEqual(cache_stats.misses, 1)
    self.assertEqual(cache_stats.read_misses, 1)
    self.assertEqual(cache_stats.write_misses, 0)
    self.assertEqual(cache_stats.coherence_misses, 0)

    # SHARED + remote write miss.
    cache1.write(6) # Remote write miss to the SHARED line.
    cache0.write(6) # Should now be INVALID so miss.
    self.assertEqual(cache_stats.hits, 1)
    self.assertEqual(cache_stats.read_hits, 1)
    self.assertEqual(cache_stats.write_hits, 0)
    self.assertEqual(cache_stats.misses, 2)
    self.assertEqual(cache_stats.read_misses, 1)
    self.assertEqual(cache_stats.write_misses, 1)
    self.assertEqual(cache_stats.coherence_misses, 1)

    # MODIFIED + remote read miss.
    cache1.read(7) # Remote read miss to the MODIFIED line.
    cache0.write(4) # Should now be SHARED so miss.
    self.assertEqual(cache_stats.hits, 1)
    self.assertEqual(cache_stats.read_hits, 1)
    self.assertEqual(cache_stats.write_hits, 0)
    self.assertEqual(cache_stats.misses, 3)
    self.assertEqual(cache_stats.read_misses, 1)
    self.assertEqual(cache_stats.write_misses, 2)
    self.assertEqual(cache_stats.coherence_misses, 2)

    # MODIFIED + remote read miss 2.
    cache1.read(7) # Remote read miss to the MODIFIED line.
    cache0.read(4) # Should now be SHARED so hit.
    self.assertEqual(cache_stats.hits, 2)
    self.assertEqual(cache_stats.read_hits, 2)
    self.assertEqual(cache_stats.write_hits, 0)
    self.assertEqual(cache_stats.misses, 3)
    self.assertEqual(cache_stats.read_misses, 1)
    self.assertEqual(cache_stats.write_misses, 2)
    self.assertEqual(cache_stats.coherence_misses, 2)

    # MODIFIED + remote write miss.
    cache0.write(5) # Prime cache (miss)
    cache1.write(7) # Remote write miss to the MODIFIED line.
    cache0.read(6) # Should now be INVALID so miss.
    self.assertEqual(cache_stats.hits, 2)
    self.assertEqual(cache_stats.read_hits, 2)
    self.assertEqual(cache_stats.write_hits, 0)
    self.assertEqual(cache_stats.misses, 5)
    self.assertEqual(cache_stats.read_misses, 2)
    self.assertEqual(cache_stats.write_misses, 3)
    self.assertEqual(cache_stats.coherence_misses, 3)

    # MODIFIED + remote write miss 2.
    cache0.write(7) # Prime cache (miss)
    cache1.write(5) # Remote write miss to the MODIFIED line.
    cache0.write(4) # Should now be INVALID so miss.
    self.assertEqual(cache_stats.hits, 2)
    self.assertEqual(cache_stats.read_hits, 2)
    self.assertEqual(cache_stats.write_hits, 0)
    self.assertEqual(cache_stats.misses, 7)
    self.assertEqual(cache_stats.read_misses, 2)
    self.assertEqual(cache_stats.write_misses, 5)
    self.assertEqual(cache_stats.coherence_misses, 4)

    # Finish off by checking P1.
    cache_stats = self.tracker.caches[1]
    self.assertEqual(cache_stats.hits, 0)
    self.assertEqual(cache_stats.read_hits, 0)
    self.assertEqual(cache_stats.write_hits, 0)
    self.assertEqual(cache_stats.misses, 8)
    self.assertEqual(cache_stats.read_misses, 4)
    self.assertEqual(cache_stats.write_misses, 4)
    self.assertEqual(cache_stats.coherence_misses, 4)

  def test_address_tracking(self):
    """Test address tracking."""

    # First do basic tests just by counting accessed address sets.

    for cache_stats in self.tracker.caches.values():
      self.assertEqual(len(cache_stats.accessed_addresses), 0)

    # Addresses 0, 1, 2, 3 only accessed by one processor (P0, ..., P4).

    self.caches[0].read(0)
    self.caches[1].write(1)
    self.caches[2].read(2)
    self.caches[3].read(3)

    for cache_stats in self.tracker.caches.values():
      self.assertEqual(len(cache_stats.accessed_addresses), 1)

    # Address 5, 6 are accessed by two processors.

    self.caches[0].read(5)
    self.caches[1].write(5)
    self.caches[2].write(6)
    self.caches[3].write(6)

    for cache_stats in self.tracker.caches.values():
      self.assertEqual(len(cache_stats.accessed_addresses), 2)

    # Address 7 accessed by three processors (P0, P1, P3).

    self.caches[0].read(7)
    self.caches[1].write(7)
    self.caches[2].read(2) # Another access to address 2.
    self.caches[3].write(7)

    self.assertEqual(len(self.tracker.caches[0].accessed_addresses), 3)
    self.assertEqual(len(self.tracker.caches[1].accessed_addresses), 3)
    self.assertEqual(len(self.tracker.caches[2].accessed_addresses), 2)
    self.assertEqual(len(self.tracker.caches[3].accessed_addresses), 3)

    # Address 8 accessed by all.

    self.caches[0].read(8)
    self.caches[1].write(8)
    self.caches[2].read(8)
    self.caches[3].write(8)

    self.assertEqual(len(self.tracker.caches[0].accessed_addresses), 4)
    self.assertEqual(len(self.tracker.caches[1].accessed_addresses), 4)
    self.assertEqual(len(self.tracker.caches[2].accessed_addresses), 3)
    self.assertEqual(len(self.tracker.caches[3].accessed_addresses), 4)

    # Now do `proper' tests with post-computed statistics.

    # First, reset.
    self.setUp()

    # Addresses accessed as above, but access type changed and sequence jumbled.
    self.caches[0].read(5)
    self.caches[3].write(6)
    self.caches[3].write(6)
    self.caches[3].read(8)
    self.caches[0].write(0)
    self.caches[0].read(5)
    self.caches[1].read(1)
    self.caches[2].read(6)
    self.caches[3].write(7)
    self.caches[3].read(3)
    self.caches[1].read(7)
    self.caches[1].read(8)
    self.caches[2].read(8)
    self.caches[0].read(7)
    self.caches[3].write(7)
    self.caches[0].read(8)
    self.caches[2].write(2)
    self.caches[1].write(5)
    self.caches[1].write(7)

    # Compute the post-processed statistics.
    stats_dict = self.tracker.get_general_stats()

    self.assertEqual(stats_dict["addressed_by_one_processor"], 4)
    self.assertEqual(stats_dict["addressed_by_two_processors"], 2)
    self.assertEqual(stats_dict["addressed_by_more_than_two_processors"], 2)


if __name__ == "__main__":
  unittest.main()