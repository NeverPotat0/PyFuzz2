__author__ = 'susperius'

import logging

import gevent
import gevent.monkey
from gevent.queue import Queue
from communication.beaconserver import BeaconServer
from communication.reportserver import ReportServer
from communication.webserver import WebServer
from model.config import ConfigParser
from worker.beaconworker import BeaconWorker
from worker.reportworker import ReportWorker
from web.main import WebSite
from urlparse import parse_qs

gevent.monkey.patch_all()

CONFIG_FILENAME = "server_config.xml"


class PyFuzz2Server:
    def __init__(self, logger, config_filename=CONFIG_FILENAME):
        self._logger = logger
        self._config = ConfigParser(config_filename)
        self._beacon_port, self._beacon_timeout = self._config.beacon_config
        self._report_port = self._config.report_server_config
        self._web_port = self._config.web_server_config
        self._beacon_queue = Queue()
        self._beacon_server = BeaconServer(self._beacon_port, self._beacon_queue)
        self._beacon_worker = BeaconWorker(self._beacon_queue, self._beacon_timeout)
        self._report_queue = Queue()
        self._report_server = ReportServer(self._report_port, self._report_queue)
        self._report_worker = ReportWorker(self._report_queue, self._beacon_worker.nodes)
        self._web_queue = Queue()
        self._web_server = WebServer(self._web_port, self._web_queue, self.web_main)

    def main(self):
        self._logger.info("PyFuzz2 Server started...")
        self._beacon_server.serve()
        self._beacon_worker.start_worker()
        self._report_server.serve()
        self._report_worker.start_worker()
        self._web_server.serve()
        while True:
            try:
                gevent.sleep(0)
            except KeyboardInterrupt:
                exit(0)

    def web_main(self, environ, start_response):
        site = WebSite()
        func = "home"
        if environ['PATH_INFO'] == "/index.py" or environ['PATH_INFO'] == "/":
            parameters = parse_qs(environ['QUERY_STRING'])
            if "func" in parameters:
                func = parameters['func'][0] if parameters['func'][0] in site.funcs else "home"
            if func == "home":
                status, headers, html = site.home(self._beacon_worker.nodes)
            elif func == "node_detail":
                if 'node' in parameters and parameters['node'][0] in self._beacon_worker.nodes.keys():
                    status, headers, html = site.node_detail(self._beacon_worker.nodes[parameters['node'][0]])
                else:
                    status, headers, html = site.file_not_found()
        elif environ['PATH_INFO'] == "/style.css":
            status, headers, html = site.get_style()
            start_response(status, headers)
        else:
            status, headers, html = site.file_not_found()
        start_response(status, headers)
        # debug
        html += "<br><br>" + str(environ) + "<br><br>" + func
        # /debug
        return html


if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    server = PyFuzz2Server(logger)
    server.main()