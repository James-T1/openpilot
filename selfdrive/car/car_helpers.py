import os
import time
from common.basedir import BASEDIR
from common.realtime import sec_since_boot
from common.fingerprints import eliminate_incompatible_cars, all_known_cars, get_shortest_fpmatch
from selfdrive.swaglog import cloudlog
import selfdrive.messaging as messaging

def load_interfaces(x):
  ret = {}
  for interface in x:
    try:
      imp = __import__('selfdrive.car.%s.interface' % interface, fromlist=['CarInterface']).CarInterface
    except ImportError:
      imp = None
    for car in x[interface]:
      ret[car] = imp
  return ret


def _get_interface_names():
  # read all the folders in selfdrive/car and return a dict where:
  # - keys are all the car names that which we have an interface for
  # - values are lists of spefic car models for a given car
  interface_names = {}
  for car_folder in [x[0] for x in os.walk(BASEDIR + '/selfdrive/car')]:
    try:
      car_name = car_folder.split('/')[-1]
      model_names = __import__('selfdrive.car.%s.values' % car_name, fromlist=['CAR']).CAR
      model_names = [getattr(model_names, c) for c in model_names.__dict__.keys() if not c.startswith("__")]
      interface_names[car_name] = model_names
    except (ImportError, IOError):
      pass

  return interface_names


# imports from directory selfdrive/car/<name>/
interfaces = load_interfaces(_get_interface_names())


# **** for use live only ****
def fingerprint(logcan, timeout):
  if os.getenv("SIMULATOR2") is not None:
    return ("simulator2", None)
  elif os.getenv("SIMULATOR") is not None:
    return ("simulator", None)

  cloudlog.warning("waiting for fingerprint...")
  candidate_cars = all_known_cars()
  finger = {}
  st = None
  st_passive = sec_since_boot()  # only relevant when passive
  it = None
  prev_finger_len = -1
  can_seen = False
  while 1:
    for a in messaging.drain_sock(logcan):
      for can in a.can:
        can_seen = True
        # ignore everything not on bus 0 and with more than 11 bits,
        # which are ussually sporadic and hard to include in fingerprints
        if can.src == 0 and can.address < 0x800:
          finger[int(can.address)] = len(can.dat)      # convert long int can address to a normal int
          candidate_cars = eliminate_incompatible_cars(can, candidate_cars)

    # set start time when first can message is seen
    if st is None and can_seen:
      st = sec_since_boot()
    # reset idle timer when fingerprint grows
    if len(finger) != prev_finger_len:
      it = None
    # set idle timer when fingerprinting stalls
    elif it is None and len(finger) == prev_finger_len:
      it = sec_since_boot()  
    # set current time
    ts = sec_since_boot()        

    # if we only have one car choice and the time_fingerprint since we stalled
    # has elapsed, exit. Toyota needs higher time_fingerprint, since DSU does not
    # broadcast immediately
    if len(candidate_cars) == 1 and st is not None:
      # TODO: better way to decide to wait more if Toyota
      time_fingerprint = 1.0 if ("TOYOTA" in candidate_cars[0] or "LEXUS" in candidate_cars[0]) else 0.1
      if (ts-st) > time_fingerprint:
        break
    # if fingerprinting has stalled with more than 1 candidate, 
    # go with the shortest fingerprint (car with lowest trim level),
    # but only when we have an adequate number of matches
    elif len(candidate_cars) > 1 and it is not None:
      if ((ts-it) > 1.0) and (len(finger) > 30):
        #print('Checking for shortest fingerprint...')
        shortest_fp = get_shortest_fpmatch(finger, candidate_cars)
        if shortest_fp is not None:
          #print('Shortest fingerprint found.')
          candidate_cars = [ candidate_cars[shortest_fp] ]
          break

    # bail if no cars left or we've been waiting too long
    elif len(candidate_cars) == 0 or (timeout and (ts - st_passive) > timeout):
      return None, finger

    # store the length of our current fingerprint if we've seen a can message
    if can_seen:
      prev_finger_len = len(finger)
    time.sleep(0.01)

  cloudlog.warning("fingerprinted %s", candidate_cars[0])
  return (candidate_cars[0], finger)


def get_car(logcan, sendcan=None, passive=True):
  # TODO: timeout only useful for replays so controlsd can start before unlogger
  timeout = 2. if passive else None
  candidate, fingerprints = fingerprint(logcan, timeout)

  if candidate is None:
    cloudlog.warning("car doesn't match any fingerprints: %r", fingerprints)
    if passive:
      candidate = "mock"
    else:
      return None, None

  interface_cls = interfaces[candidate]

  if interface_cls is None:
    cloudlog.warning("car matched %s, but interface wasn't available or failed to import" % candidate)
    return None, None

  params = interface_cls.get_params(candidate, fingerprints)

  return interface_cls(params, sendcan), params
