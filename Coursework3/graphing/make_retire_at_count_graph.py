import math
import matplotlib.pyplot as plt
import numpy as np
import sys


def divide_scalar_by(seq, scalar):
  float_scalar = float(scalar)

  return map(lambda element : float_scalar / element, seq)


def main():
  if len(sys.argv) != 2:
    print "Usage: %s data_file" % sys.argv[0]
    return

  # 5 stats in the line info graph. 
  N = 5

  with open(sys.argv[1], "r") as f:
    lines = [line.strip() for line in f]
    if len(lines) != 1:
      raise ValueError("Expected 1 line, found %s." % len(data))
    values = map(float, lines[0].split())
    if len(values) != (N + 1):
      raise ValueError("Unexpected number of parts in line '%s'" % lines[0])

  # The values should be taken relative to the SC.
  sequential_consistency_value = values[0]
  values = divide_scalar_by(values, sequential_consistency_value)

  # Strip off the SC.
  values = values[1:]

  indices = np.arange(N) + 0.5
  width = 0.8

  fig = plt.figure()
  ax = fig.add_subplot(111)
  ax.bar(indices, values, width, color='#729FCF', align='center')

  ax.set_title("Effect of altering retire-at count")
  ax.set_ylabel('Speedup over Sequential Consistency')
  y_ticks = range(0, 40)
  y_ticks = map(lambda x : x / 20.0, y_ticks)
  ax.set_yticks(y_ticks)
  ax.set_xticks(indices)
  ax.set_xticklabels(('TSO [32, 1]',
      'TSO [32, 2]',
      'TSO [32, 4]',
      'TSO [32, 8]',
      'TSO [32, 16]'))

  ax.axis([0, N, 1.05, 1.35])

  plt.show()

if __name__ == "__main__":
  main()