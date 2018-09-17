#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from hermes_python.hermes import Hermes
import  os
from snipshue.snipshue import SnipsHue
from snipshelpers.thread_handler import ThreadHandler
from snipshelpers.config_parser import SnipsConfigParser
import Queue

CONFIGURATION_ENCODING_FORMAT = "utf-8"
CONFIG_INI =  "config.ini"

MQTT_IP_ADDR = "localhost"
MQTT_PORT = 1883
MQTT_ADDR = "{}:{}".format(MQTT_IP_ADDR, str(MQTT_PORT))

API_KEY = "api_key"
_id = "snips-skill-hue"


class Skill:
    def __init__(self):
        try:
            config = SnipsConfigParser.read_configuration_file(CONFIG_INI)
        except :
            config = None
        hostname = None
        code = None
        if config and config.get('secret') is not None:
            if config.get('secret').get('hostname') is not None:
                hostname = config.get('secret').get('hostname')
                if hostname == "":
                    hostname = None
            if config.get('secret').get(API_KEY) is not None:
                code = config.get('secret').get(API_KEY)
                if code == "":
                    code = None
        if hostname is None or code is None:
            print('No configuration')
        self.snipshue = SnipsHue(hostname, code)
        hostname = self.snipshue.hostname
        code  = self.snipshue.username
        self.update_config(CONFIG_INI, config, hostname, code)
        self.queue = Queue.Queue()
        self.thread_handler = ThreadHandler()
        self.thread_handler.run(target=self.start_blocking)
        self.thread_handler.start_run_loop()

    def update_config(self, filename, data, hostname, code):
        if 'secret' not in data or data['secret'] is None:
            data['secret'] = {}
        data['secret']['hostname'] = hostname
        data['secret'][API_KEY] = code
        SnipsConfigParser.write_configuration_file(filename, data)

    def start_blocking(self, run_event):
        while run_event.is_set():
            try:
                self.queue.get(False)
            except Queue.Empty:
                with Hermes(MQTT_ADDR) as h:
                    h.subscribe_intents(self.callback).start()

    ####    section -> extraction of slot value
    def extract_house_rooms(self, intent_message):
        house_rooms = []
        if intent_message.slots.house_room is not None:
            for room in intent_message.slots.house_room:
                house_rooms.append(room.slot_value.value.value)
        return house_rooms
    def extract_percentage(self, intent_message, default_percentage):
        percentage = default_percentage
        if intent_message.slots.percent:
            percentage = intent_message.slots.percent.first()
        if percentage < 0:
            percentage = 0
        if percentage > 100:
            percentage = 100
        return percentage

    def extract_color(self, intent_message):
        color_code = None
        if intent_message.slots.color:
            color_code = intent_message.slots.color.first().value
        return color_code
    def extract_scene(self, intent_message):
        scene_code = None
        if intent_message.slots.scene:
            scene_code = intent_message.slots.scene.first().value
        return scene_code
    ####    section -> handlers of intents
    def callback(self, hermes, intent_message):
        print("[HUE] Received")
        rooms = self.extract_house_rooms(intent_message)
        if intent_message.intent.intent_name == 'coorfang:turnOn':
            self.queue.put(self.turn_on(hermes, intent_message, rooms))
        if intent_message.intent.intent_name == 'coorfang:turnOff':
            self.queue.put(self.turn_off(hermes, intent_message, rooms))
        if intent_message.intent.intent_name == 'coorfang:setBrightness':
            self.queue.put(self.set_brightness(hermes, intent_message, rooms))
        if intent_message.intent.intent_name == 'coorfang:setColor':
            self.queue.put(self.set_color(hermes, intent_message, rooms))
        if intent_message.intent.intent_name == 'coorfang:setScene':
            self.queue.put(self.set_scene(hermes, intent_message, rooms))
        if intent_message.intent.intent_name == 'coorfang:shiftUp':
            self.queue.put(self.shift_up(hermes, intent_message, rooms))
        if intent_message.intent.intent_name == 'coorfang:shiftDown':
            self.queue.put(self.shift_down(hermes, intent_message, rooms))

    def turn_on(self, hermes, intent_message, rooms):
        if len(rooms) > 0:
            for room in rooms:
                self.snipshue.light_on(room)
        else:
            self.snipshue.light_on(None)
        self.terminate_feedback(hermes, intent_message)

    def turn_off(self, hermes, intent_message, rooms):
        if len(rooms) > 0:
            for room in rooms:
                self.snipshue.light_off(room)
        else:
            self.snipshue.light_off(None)
        self.terminate_feedback(hermes, intent_message)

    def set_brightness(self, hermes, intent_message, rooms):
        percent = self.extract_percentage(intent_message, 80)
        if len(rooms) > 0:
            for room in rooms:
                self.snipshue.light_brightness(percent, room)
        else:
            self.snipshue.light_brightness(percent, None)
        self.terminate_feedback(hermes, intent_message)

    def set_color(self, hermes, intent_message, rooms):
        color = self.extract_color(intent_message)

        print color
        print type(color)

        if len(rooms) > 0:
            for room in rooms:
                self.snipshue.light_color(color, room)
        else:
            self.snipshue.light_color(color, None)

        self.terminate_feedback(hermes, intent_message)

    def set_scene(self, hermes, intent_message, rooms):
        scene = self.extract_scene(intent_message)
        if len(rooms) > 0:
            for room in rooms:
                self.snipshue.light_scene(scene, room)
        else:
            self.snipshue.light_scene(scene, None)
        self.terminate_feedback(hermes, intent_message)

    def shift_up(self, hermes, intent_message, rooms):
        percent = self.extract_percentage(intent_message, 20)
        if len(rooms) > 0:
            for room in rooms:
                self.snipshue.light_up(percent, room)
        else:
            self.snipshue.light_up(percent, None)
        self.terminate_feedback(hermes, intent_message)

    def shift_down(self, hermes, intent_message, rooms):
        percent = self.extract_percentage(intent_message, 20)
        if len(rooms) > 0:
            for room in rooms:
                self.snipshue.light_down(percent, room)
        else:
            self.snipshue.light_down(percent, None)
        self.terminate_feedback(hermes, intent_message)

    ####    section -> feedback reply // future function
    def terminate_feedback(self, hermes, intent_message, mode='default'):
        if mode == 'default':
            hermes.publish_end_session(intent_message.session_id, None)
        else:
            #### more design
            hermes.publish_end_session(intent_message.session_id, None)

if __name__ == "__main__":
    Skill()