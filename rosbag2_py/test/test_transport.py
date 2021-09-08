# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import os
import sys
import threading
import yaml
from pathlib import Path

from common import get_rosbag_options  # noqa
import rclpy
from rclpy.qos import QoSProfile
from std_msgs.msg import String

if os.environ.get('ROSBAG2_PY_TEST_WITH_RTLD_GLOBAL', None) is not None:
    # This is needed on Linux when compiling with clang/libc++.
    # TL;DR This makes class_loader work when using a python extension compiled with libc++.
    #
    # For the fun RTTI ABI details, see https://whatofhow.wordpress.com/2015/03/17/odr-rtti-dso/.
    sys.setdlopenflags(os.RTLD_GLOBAL | os.RTLD_LAZY)

import rosbag2_py  # noqa


class MinimalPublisher(Node):

    def __init__(self):
        super().__init__('minimal_publisher')
        self.publisher_ = self.create_publisher(String, 'test', 10)
        self.i = 0
        msg = String()
        msg.data = "Testing mesage"
        while(self.i < 10):
            self.publisher_.publish(msg)
            time.sleep(1)
            self.i += 1


def test_options_qos_conversion():
    # Tests that the to-and-from C++ conversions are working properly in the pybind structs
    simple_overrides = {
        '/topic': QoSProfile(depth=10)
    }

    play_options = rosbag2_py.PlayOptions()
    play_options.topic_qos_profile_overrides = simple_overrides
    assert play_options.topic_qos_profile_overrides == simple_overrides

    record_options = rosbag2_py.RecordOptions()
    record_options.topic_qos_profile_overrides = simple_overrides
    assert record_options.topic_qos_profile_overrides == simple_overrides


def test_record_cancel(tmp_path):
    bag_path = str(tmp_path / 'test_record_cancel')
    storage_options, converter_options = get_rosbag_options(bag_path)

    recorder = rosbag2_py.Recorder()

    record_options = rosbag2_py.RecordOptions()
    record_options.all = True
    record_options.is_discovery_disabled = False
    record_options.rmw_serialization_format = ""
    record_options.topic_polling_interval = datetime.timedelta(milliseconds=100)

    record_options.compression_mode = 'none'
    record_options.compression_queue_size = 1
    record_options.compression_threads = 0

    rclpy.init()
    record_thread = threading.Thread(
        target=recorder.record,
        args=(storage_options, record_options),
        daemon=True)
    record_thread.start()

    node = rclpy.create_node('demo_guard_condition')
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(node)
    pub = node.create_publisher(String, 'chatter', 10)

    i = 0
    import time
    while rclpy.ok() and i < 10:
        msg = String()
        msg.data = 'Hello World: {0}'.format(i)
        i += 1
        pub.publish(msg)
        time.sleep(0.1)
        # executor.spin_once()

    recorder.cancel()
    # Without either of this line, it does not create the metadata.yaml.
    # Makes me wonder if the cancel works...
    # node.destroy_node()
    # rclpy.shutdown()

    assert (Path(bag_path) / 'metadata.yaml').exists()
    assert (Path(bag_path) / 'test_record_cancel_0.db3').exists()

    #TODO check the file content
