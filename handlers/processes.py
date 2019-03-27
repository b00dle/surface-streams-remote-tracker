"""
This is the processes module and supports all the ReST actions for the
PROCESSES collection
"""

# System modules
from datetime import datetime
import uuid
import os
import shutil

# 3rd party modules
from flask import make_response, abort
from processes.surface_tracker import SurfaceTracker


class _Process(object):
    def __init__(self, uuid, user_id, server_ip, tuio_port, frame_port,
                 frame_width, frame_protocol, tracking_config=""):
        self.uuid = uuid
        self.user_id = user_id
        self.server_ip = server_ip
        self.tuio_port = tuio_port
        self.frame_port = frame_port
        self.frame_width = frame_width
        self.frame_protocol = frame_protocol
        self.tracking_config = tracking_config
        self._is_running = False
        self._tracker = None

    def is_running(self):
        return self._is_running

    def start(self):
        if self.is_running() or len(self.tracking_config) == 0:
            return
        self._tracker = SurfaceTracker(
            server_ip=self.server_ip, server_tuio_port=self.tuio_port,
            frame_port=self.frame_port, frame_width=self.frame_width,
            frame_protocol=self.frame_protocol, patterns_config=self.tracking_config,
            user_id=self.user_id
        )
        self._tracker.start()
        self._is_running = True

    def stop(self):
        if not self.is_running():
            return
        self._tracker.stop()
        self._is_running = False

    @staticmethod
    def _is_dict_key(key):
        return not key.startswith('__') and not key.startswith('_') and not callable(key)

    def as_dict(self):
        return {key:value for key, value in self.__dict__.items() if _Process._is_dict_key(key)}


def create_timestamp():
    return datetime.now().strftime(("%Y-%m-%d %H:%M:%S"))


def create_uuid():
    return str(uuid.uuid4())


PROCESS_LIMIT = 3
PROCESSES = {}


def remove_one(uuid):
    if uuid not in PROCESSES:
        return

    PROCESSES[uuid].stop()
    if os.path.exists("SERVER_DATA/" + str(uuid)):
        shutil.rmtree("SERVER_DATA/" + str(uuid), ignore_errors=True)

    del PROCESSES[uuid]


def remove_all():
    for uuid in [u for u in PROCESSES.keys()]:
        remove_one(uuid)


def create_process(user_id, server_ip, tuio_port, frame_port, frame_width, frame_protocol):
    num_processes = len(PROCESSES)

    frame_port = frame_port if frame_port > 0 else 9001 + num_processes
    # 5001 is the default port for tuio on surface streams server
    tuio_port = tuio_port if tuio_port > 0 else 5001
    user_id = user_id if user_id > 0 else 1 + num_processes

    p = _Process(
        uuid=create_uuid(), user_id=user_id,
        server_ip=server_ip, tuio_port=tuio_port,
        frame_port=frame_port, frame_width=frame_width,
        frame_protocol=frame_protocol
    )

    PROCESSES[p.uuid] = p

    return p.as_dict()


def attach_tracking_config(uuid, tracking_config):
    if not os.path.exists("SERVER_DATA/" + str(uuid)):
        os.mkdir("SERVER_DATA/" + str(uuid))

    filename = "SERVER_DATA/" + str(uuid) + "/" + tracking_config.filename

    p = PROCESSES[uuid]
    if len(PROCESSES[uuid].tracking_config) > 0:
        if os.path.exists(PROCESSES[uuid].tracking_config):
            os.remove(PROCESSES[uuid].tracking_config)
    p.tracking_config = filename

    tracking_config.save(filename)


def read_all():
    res = [p.as_dict() for p in PROCESSES.values()]
    return res


def read_one(uuid):
    if uuid not in PROCESSES:
        abort(
            404,
            "Process with uuid {uuid} not found".format(uuid=uuid)
        )
    res = PROCESSES[uuid].as_dict()
    return res


def create(process, tracking_config=None):
    if len(PROCESSES) >= PROCESS_LIMIT:
        abort(
            406,
            "Process list already at maximum capacity"
        )

    if tracking_config is not None:
        mimetype = tracking_config.mimetype
        if mimetype != "application/json":
            abort(
                406,
                "Wrong mimetype. Expected application/json. Got {mime} not found".format(mime=mimetype)
            )

    user_id = process.get("user_id", -1)
    server_ip = process.get("server_ip", "0.0.0.0")
    tuio_port = process.get("tuio_port", -1)
    frame_port = process.get("frame_port", -1)
    frame_width = process.get("frame_width", 640)
    frame_protocol = process.get("frame_protocol", -1)

    p_dict = create_process(
        user_id, server_ip, tuio_port, frame_port,
        frame_width, frame_protocol
    )

    if tracking_config is not None:
        attach_tracking_config(uuid=p_dict["uuid"], tracking_config=tracking_config)
        p = PROCESSES[p_dict["uuid"]]
        p.start()
        p_dict = p.as_dict()

    return p_dict


def update_config(uuid, tracking_config):
    if uuid not in PROCESSES:
        abort(
            404,
            "Process with uuid {uuid} not found".format(uuid=uuid)
        )

    mimetype = tracking_config.mimetype
    if mimetype != "application/json" and not tracking_config.filename.endswith(".json"):
        abort(
            406,
            "Wrong mimetype. Expected application/json. Got {mime} not found".format(mime=mimetype)
        )

    attach_tracking_config(uuid, tracking_config)

    # TODO post update to process if running
    p = PROCESSES[uuid]
    if p.is_running():
        p.stop()
    p.start()

    return make_response(
        "Successfully updated process at uuid={uuid}".format(uuid=uuid), 200
    )


def delete(uuid):
    if uuid not in PROCESSES:
        abort(
            404,
            "Process with uuid {uuid} not found".format(uuid=uuid)
        )

    remove_one(uuid)

    #if True:
    return make_response(
        "Process successfully deleted at uuid={uuid}".format(uuid=uuid), 200
    )
    #else:
    #    abort(
    #        406,
    #        "could not delete Process at uuid={uuid}".format(uuid=uuid)
    #    )


def upload_resource(uuid, data):
    if uuid not in PROCESSES:
        abort(
            404,
            "Process with uuid {uuid} not found".format(uuid=uuid)
        )

    if not os.path.exists("SERVER_DATA/" + str(uuid)):
        os.mkdir("SERVER_DATA/" + str(uuid))

    filename = "SERVER_DATA/" + str(uuid) + "/" + data.filename
    data.save(filename)

    return make_response(
        "Successfully uploaded resource {name} for process at uuid={uuid}".format(name=data.filename, uuid=uuid), 200
    )
