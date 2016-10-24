from flask import Flask, render_template, send_file, abort, request, flash
from table import SingleNodeTable, NodeTable
from gevent.queue import Queue
from node.model.config import ConfigParser
from node.model.message_types import MESSAGE_TYPES


class WebInterface:
    def __init__(self, web_queue, node_dict, crash_dict):
        self._inc_confs = 0  # keep track of the actual open in and out going config files
        self._out_confs = 0
        self._web_queue = web_queue
        self._node_dict = node_dict
        self._crash_dict = crash_dict
        self.app = Flask(__name__)
        self.app.add_url_rule("/", "index", self.index_site)
        self.app.add_url_rule("/index.html", "index", self.index_site)
        self.app.add_url_rule("/stats.html", "stats", self.stats_site)
        self.app.add_url_rule("/about.html", "about", self.about_site)
        self.app.add_url_rule("/node/<string:addr>", 'node_detail', self.node_detail)
        self.app.add_url_rule("/node/<string:addr>/download", 'node_get_config', self.node_get_config)
        self.app.add_url_rule("/node/<string:addr>/upload", 'node_set_config', self.node_set_config, methods=['POST'])
        self.app.add_url_rule("/node/<string:addr>/reboot", 'node_reboot', self.node_reboot)

    def index_site(self):
        table_items = []
        for node in self._node_dict.items():
            table_items.append(node[1].info)
        table_items.sort()
        node_table = NodeTable(table_items)
        return render_template("main.html", section_title="OVERVIEW", body_space=node_table)

    def stats_site(self):
        return render_template("main.html", section_title="STATS")

    def about_site(self):
        return render_template("main.html", section_title="ABOUT")

    def node_detail(self, addr):
        if addr not in self._node_dict.keys():
            abort(404)
        node = self._node_dict[addr]
        href_base = "/node/" + addr + "/"
        node_info_items = [{'descr': 'NAME', 'value': node.info['name']},
                           {'descr': 'IP ADDRESS', 'value': node.info['addr']},
                           {'descr': 'STATUS', 'value': node.info['status']},
                           {'descr': 'LAST CONTACT', 'value': node.info['last_contact']},
                           {'descr': 'CRASHES', 'value': node.info['crashes']}]
        node_info_table = SingleNodeTable(node_info_items)
        if node.config is not None:
            node_config = ConfigParser(node.config, True)
            general_config, programs, op_mode_conf = node_config.dump_additional_information()
            general_config_items = []
            for item in general_config:
                general_config_items.append({'descr': item[0], 'value': item[1]})
            count = 1
            program_items = []
            for prog in programs:
                program_items.append({'descr': 'Program ' + str(count), 'value': prog})
                count += 1
            op_mode_items = []
            if node_config.node_op_mode == "fuzzing":
                general_config_items.append({'descr': 'OP-Mode', 'value': "Fuzzing"})
                op_mode_items.append({'descr': 'Fuzzer Type', 'value': op_mode_conf['fuzzer_type']})
                for item in op_mode_conf['fuzz_conf'].items():
                    op_mode_items.append({'descr': item[0], 'value': item[1]})
            elif node.op_mode == "reducing":
                pass
            else:
                op_mode_items.append({'descr': 'OP-Mode', 'value': 'Not found'})
            general_config_table = SingleNodeTable(general_config_items)
            program_table = SingleNodeTable(program_items)
            op_mode_conf_table = SingleNodeTable(op_mode_items)
            return render_template("single_node.html", section_title="NODE DETAIL", node_info_table=node_info_table,
                                   general_config_table=general_config_table, program_table=program_table,
                                   op_mode_conf_table=op_mode_conf_table, href_base=href_base)
        else:
            return render_template("single_node.html", section_title="NODE DETAIL", body_space=node_info_table,
                                   href_base=href_base)

    def node_get_config(self, addr):
        if addr not in self._node_dict.keys():
            abort(404)
        else:
            node = self._node_dict[addr]
            if node.config is None:
                flash("Config not found")
                return self.node_detail(addr)
            else:
                with open("tmp/node_config.xml", 'w+') as fd:
                    fd.write(node.config)
                return send_file("tmp/node_config.xml")

    def node_set_config(self, addr):
        if "conf_file" not in request.files:
            abort(404)
        file = request.files['conf_file']
        file.save("tmp/inc_conf.xml")
        print file
        #TODO: do all the necessary stuff in order to change node config
        return self.node_detail(addr)

    def node_reboot(self, addr):
        if addr not in self._node_dict.keys():
            abort(404)
        else:
            node = self._node_dict[addr]
            node.status = False
            self._web_queue.put([(addr, node.listener_port), MESSAGE_TYPES['RESET'], ""])
            return self.node_detail(addr)

if __name__ == "__main__":
    from model.pyfuzz2_node import PyFuzz2Node
    node_dict = {}
    node_conf = ""
    with open("../node/node_config.xml") as fd:
        node_conf = fd.read()
    for i in range(10,30):
        new_node = PyFuzz2Node("NODE" + str(i), "192.168.1."+str(i), 31337)
        new_node.crashed(i)
        new_node.config = node_conf
        node_dict["192.168.1." + str(i)] = new_node
    intf = WebInterface(Queue(), node_dict, {})
    intf.app.run("127.0.0.1", 8080, debug=True)
