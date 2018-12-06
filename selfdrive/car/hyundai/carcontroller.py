from selfdrive.car import limit_steer_rate
from selfdrive.boardd.boardd import can_list_to_can_capnp
from selfdrive.car.hyundai.hyundaican import create_lkas11, create_lkas12, \
                                             create_1191, create_1156, \
                                             create_clu11, create_mdps12
from selfdrive.car.hyundai.values import Buttons
from selfdrive.can.packer import CANPacker
#import numpy as np

# Steer torque limits

class SteerLimitParams:
  STEER_MAX = 250   # 409 is the max
  STEER_DELTA_UP = 3
  STEER_DELTA_DOWN = 4  # 7 originally, ku7 has it as 4
  STEER_DRIVER_ALLOWANCE = 50
  STEER_DRIVER_MULTIPLIER = 2
  STEER_DRIVER_FACTOR = 1

class CarController(object):
  def __init__(self, dbc_name, car_fingerprint, enable_camera):
    self.apply_steer_last = 0
    self.car_fingerprint = car_fingerprint
    self.lkas11_cnt = 0
    self.mdps12_cnt = 0
    self.cnt = 0
    self.last_resume_cnt = 0
    self.enable_camera = enable_camera
    # True when camera present, and we need to replace all the camera messages
    # otherwise we forward the camera msgs and we just replace the lkas cmd signals
    self.camera_disconnected = False

    self.packer = CANPacker(dbc_name)

  def update(self, sendcan, enabled, CS, actuators, pcm_cancel_cmd, hud_alert):

    if not self.enable_camera:
      return

    ### Steering Torque
    apply_steer = int(round(actuators.steer * SteerLimitParams.STEER_MAX))

    # Limit steer rate for safety
    #apply_steer = apply_std_steer_torque_limits(apply_steer, self.apply_steer_last, CS.steer_torque_driver, SteerLimitParams)
    apply_steer = limit_steer_rate(apply_steer, self.apply_steer_last, SteerLimitParams)

    if not enabled:
      apply_steer = 0

    steer_req = 1 if enabled else 0

    self.apply_steer_last = apply_steer

    can_sends = []

    self.lkas11_cnt = self.cnt % 0x10
    self.clu11_cnt = self.cnt % 0x10
    self.mdps12_cnt = self.cnt % 0x100

    if self.camera_disconnected:
      if (self.cnt % 10) == 0:
        can_sends.append(create_lkas12())
      if (self.cnt % 50) == 0:
        can_sends.append(create_1191())
      if (self.cnt % 7) == 0:
        can_sends.append(create_1156())

#    can_sends.append(create_lkas11(self.packer, self.car_fingerprint, apply_steer, steer_req, self.lkas11_cnt, \
#                                   enabled, CS.lkas11, hud_alert, (CS.cstm_btns.get_button_status("cam") > 0), keep_stock=(not self.camera_disconnected)))
#   Going to set use_stock = True so if OP is disabled it will use the stock LKAS system.
    can_sends.append(create_lkas11(self.packer, self.car_fingerprint, apply_steer, steer_req, self.lkas11_cnt, \
                                   enabled, CS.lkas11, hud_alert, True, keep_stock=(not self.camera_disconnected)))

    can_sends.append(create_mdps12(self.packer, self.mdps12_cnt, CS.mdps12, CS.lkas11, CS.camcan))


    if pcm_cancel_cmd:
      can_sends.append(create_clu11(self.packer, CS.clu11, Buttons.CANCEL))
    elif CS.stopped and (self.cnt - self.last_resume_cnt) > 5:
      self.last_resume_cnt = self.cnt
      can_sends.append(create_clu11(self.packer, CS.clu11, Buttons.RES_ACCEL))

    ### Send messages to canbus
    sendcan.send(can_list_to_can_capnp(can_sends, msgtype='sendcan').to_bytes())

    self.cnt += 1
