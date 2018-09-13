import os
from common.basedir import BASEDIR

def get_fingerprint_list():
  # read all the folders in selfdrive/car and return a dict where:
  # - keys are all the car models for which we have a fingerprint
  # - values are lists dicts of messages that constitute the unique 
  #   CAN fingerprint of each car model and all its variants
  fingerprints = {}
  for car_folder in [x[0] for x in os.walk(BASEDIR + '/selfdrive/car')]:
    try:
      car_name = car_folder.split('/')[-1]
      values = __import__('selfdrive.car.%s.values' % car_name, fromlist=['FINGERPRINTS'])
      if hasattr(values, 'FINGERPRINTS'):
        car_fingerprints = values.FINGERPRINTS
      else:
        continue
      for f, v in car_fingerprints.items():
        fingerprints[f] = v
    except (ImportError, IOError):
      pass
  #print(fingerprints)
  return fingerprints


_FINGERPRINTS = get_fingerprint_list()

_DEBUG_ADDRESS = {1880: 8}   # reserved for debug purposes

def is_valid_for_fingerprint(msg, car_fingerprint):
  adr = msg.address
  bus = msg.src
  # ignore addresses that are more than 11 bits
  return (adr in car_fingerprint and car_fingerprint[adr] == len(msg.dat)) or \
         bus != 0 or adr >= 0x800


def eliminate_incompatible_cars(msg, candidate_cars):
  """Removes cars that could not have sent msg.

     Inputs:
      msg: A cereal/log CanData message from the car.
      candidate_cars: A list of cars to consider.

     Returns:
      A list containing the subset of candidate_cars that could have sent msg.
  """
  compatible_cars = []

  for car_name in candidate_cars:
    car_fingerprints = _FINGERPRINTS[car_name]

    for fingerprint in car_fingerprints:
      fingerprint.update(_DEBUG_ADDRESS)  # add alien debug address

      if is_valid_for_fingerprint(msg, fingerprint):
        compatible_cars.append(car_name)
        break

  #print(compatible_cars)
  return compatible_cars


def all_known_cars():
  """Returns a list of all known car strings."""
  return _FINGERPRINTS.keys()


def get_shortest_fpmatch(finger, candidate_cars):
  """Finds the shortest valid match for a car fingerprint.

     Inputs:
      finger: A fingerprint dictionary for the car we're trying to match to a candidate.
      candidate_cars:  A list of cars that match all of the fingerprints we have so far.

     Returns:
      The integer index of the shortest valid fingerprint in candidate_cars, or None if no valid fingerprints exist.
      If there are multiple valid shortest fingerprints, the first one found will be returned.  
    
     Use a sanity check on fingerprint length before sending a fingerprint to this function.
  """
  shortest_fp = None
  for i, car_name in enumerate(candidate_cars):
    car_fingerprints = _FINGERPRINTS[car_name]
    for fingerprint in car_fingerprints:
      valid = True
      for adr in finger:
        # check if this fingerprint is actually valid since multiple fingerprints can live under a single car
        if not (adr in fingerprint and fingerprint[adr] == finger[adr]):
          valid = False
          break
      if not valid: continue
      # if fingerprint is valid, check to see if it is the shortest we have seen so far
      if not shortest_fp or (len(fingerprint) < shortest_fp[0]):
        shortest_fp = [len(fingerprint), i]  

  if shortest_fp is not None:
    return shortest_fp[1]
  else:
    return None
