import random

from model.JsDocument import *
from model.JsDomElement import *
from model.JsGlobal import JsGlobal
from model.DomObjectTypes import *
from model.HtmlObjects import *
from model.JsWindow import *
from html5 import Html5Fuzzer
from css import CssFuzzer
from canvas import CanvasFuzzer
from model.values import FuzzValues
from model.CssProperties import CSS_STYLES
from ..fuzzer import Fuzzer

__author__ = 'susperius'

TEMPLATE_FILE = "fuzzing/model/template.dat"


class JsDomFuzzer(Fuzzer):
    NAME = "js_dom_fuzzer"
    CONFIG_PARAMS = ["starting_elements", "total_operations", "browser", "seed", "canvas_size", "file_type"]
    CALLING_COMMENT = "//FUNCTION_CALLING"
    TIMEOUT = 20

    def __init__(self, starting_elements, total_operations, browser, seed, canvas_size, file_type='html'):
        self._starting_elements = int(starting_elements)
        self._total_operations = int(total_operations)
        self._browser = browser
        seed = int(seed)
        #  self._html_fuzzer = HtmlFuzzer(self._starting_elements, 3, seed)
        self._html_fuzzer = Html5Fuzzer(int(seed), self._starting_elements, 10, 5, file_type)
        self._css_fuzzer = CssFuzzer(seed)
        self._canvas_fuzzer = CanvasFuzzer(int(canvas_size))
        if seed == 0:
            random.seed()
        else:
            random.seed(seed)
        self._file_type = file_type
        self._function_count = 0
        self._operations_count = 0
        self._js_elements = {}
        """:type dict(JsElement)"""
        self._occurring_events = {}
        for event in DomObjectTypes.DOM_EVENTS:
            self._occurring_events[event] = 0
        self._html_page = None
        self._calls_in_startup = []
        # arrays dictionary layout: {'array_id': [JsObject, .... JsObject], ...}
        self._arrays = {}

    @classmethod
    def from_list(cls, params):
        return cls(params[0], params[1], params[2], params[3], params[4], params[5])

    @property
    def prng_state(self):
        return random.getstate()

    @property
    def file_type(self):
        return self._file_type

    def set_seed(self, seed=0):
        random.seed(seed)

    def __re_init(self):
        self._function_count = 0
        self._operations_count = 0
        self._function_count = 0
        self._operations_count = 0
        self._js_elements = {}
        self._calls_in_startup = []
        self._arrays = []
        self._occurring_events = {}
        for event in DomObjectTypes.DOM_EVENTS:
            self._occurring_events[event] = 0

    def create_testcases(self, count, directory):
        for i in range(count):
            test_name = "/test" + str(i) if i > 9 else "/test0" + str(i)
            with open(directory + test_name + "." + self._file_type, "wb+") as html_fd, open(directory + test_name + ".css", "wb+") as css_fd:
                html, css = self.fuzz()
                html = html.replace("TESTCASE", test_name)
                html_fd.write(html)
                css_fd.write(css)

    def fuzz(self):
        self._html_page = self._html_fuzzer.fuzz()
        html = self._html_page.get_raw_html()
        self._css_fuzzer.set_tags(self._html_page.get_elements_by_html_tag().keys())
        css = self._css_fuzzer.fuzz()
        js_code = ""
        js_code += self.__create_canvas_functions()
        js_code += self.__create_startup()
        while self._total_operations > self._operations_count:
            js_code += self.__add_function()
        js_code += self.__add_event_dispatcher()
        js_code += self.__create_event_handlers()
        js_code = js_code.replace(self.CALLING_COMMENT, self.__concate_startup_list())
        doc = html.replace("SCRIPT_BODY", js_code)
        self.__re_init()
        return doc, css

    def set_state(self, state):
        random.setstate(state)

    def __create_startup(self):
        code = "function startup() {\n"
        i = 0
        for elem_id in self._html_page.get_element_ids():
            code += "\t" + "elem" + str(i) + " = " + JsDocument.getElementById(elem_id) + "\n"
            self._js_elements["elem"+str(i)] = JsDomElement("elem" + str(i), self._html_page.get_element_by_id(elem_id))
            i += 1
        code += "\t" + self.CALLING_COMMENT + \
                "\n\tevent_firing();\n}\n"
        return code

    def __create_canvas_functions(self):
        code = ""
        for canvas_id in (self._html_page.get_elements_by_html_tag())['canvas']:
            self._calls_in_startup.append("\tfunc_" + canvas_id + "();")
            self._canvas_fuzzer.set_canvas_id(canvas_id)
            code += self._canvas_fuzzer.fuzz()
        return code

    def __add_function(self, func_name=None, event=False):
        if not func_name:
            func_name = "func_" + str(self._function_count) + "()"
        code = "function " + func_name + " {\n"
        func_count = random.randint(10, 50)
        for i in range(func_count):
            code += "\t" + JsGlobal.try_catch_block(self.__add_element_method())
        if not event:
            self._function_count += 1
            if random.randint(0, 10) <= 3:
                code += "\t" + JsWindow.setTimeout("func_" + str(self._function_count) + "()", self.TIMEOUT) + "\n"
            else:
                self._calls_in_startup.append("\tfunc_" + str(self._function_count) + "();")
        code += "}\n"
        return code

    def __create_event_handlers(self):
        code = ""
        for event in self._occurring_events:
            code += self.__add_function(event + "_handler" + "(event)", True)
        return code

    def __add_event_dispatcher(self):
        code = "function event_firing() {\n"
        for key in self._js_elements:
            for event in self._js_elements[key].registered_events.keys():
                if 'DOM' in event:
                    continue
                elif event == 'click':
                    code += JsGlobal.try_catch_block(self._js_elements[key].click() + "\n", "ex")
                elif event == 'error':
                    pass
                elif event == 'load':
                    pass
                elif event == 'scroll':
                    code += JsGlobal.try_catch_block(self._js_elements[key].scrollLeft() + " = 10;" + "\n", "ex")
                elif event == 'resize' or event == 'change':
                    code += JsGlobal.try_catch_block(self._js_elements[key].innerHtml() + " = \"" + "A" * 100 + "\";\n", "ex")
                elif event == 'focus' or event == 'focusin':
                    code += JsGlobal.try_catch_block(self._js_elements[key].focus() + "\n", "ex")
                elif event == 'blur':
                    code += JsGlobal.try_catch_block(self._js_elements[key].blur() + "\n", "ex")
                elif event == 'select':
                    code += JsGlobal.try_catch_block(self._js_elements[key].select() + "\n", "ex")
        code += "}\n"
        return code

    def __add__new_element(self):
        elem_name = "elem_cr" + str(len(self._js_elements))
        html_type = random.choice(HTML_OBJECTS)
        code = elem_name + " = " + JsDocument.createElement(html_type) + "\n"
        self._js_elements[elem_name] = JsDomElement(elem_name, html_type)
        return elem_name, code, html_type

    def __add_element_method(self, key=None):
        code = ""
        if not key:
            key = random.choice(self._js_elements.keys())
        method = random.choice(DomObjectTypes.DOM_ELEMENT_FUZZ_STUFF)
        if method == 'addEventListener':
            event = random.choice(DomObjectTypes.DOM_EVENTS)
            self._occurring_events[event] += 1
            code += self._js_elements[key].addEventListener(event, event + "_handler")
        elif method == 'appendChild':
            if random.randint(1, 100) < 80:
                child = random.choice(self._js_elements.keys())
                if child == key:
                    elem_name, add_code, html_type = self.__add__new_element()
                    code += add_code
                    self._js_elements[elem_name] = JsDomElement(elem_name, self._js_elements[key].html_type)
                    child = elem_name
                code += self._js_elements[key].appendChild(child)
            else:
                elem_name, add_code, html_type = self.__add__new_element()
                code += add_code
                self._js_elements[elem_name] = JsDomElement(elem_name, html_type)
                code += self._js_elements[key].appendChild(elem_name)
        elif method == 'cloneNode':
            length = len(self._js_elements)
            elem_name = "elem_cr" + str(length)
            code += elem_name + " = " + self._js_elements[key].cloneNode(True)
            self._js_elements[elem_name] = JsDomElement(elem_name, self._js_elements[key].html_type)
            self._js_elements[elem_name].set_children(self._js_elements[key].get_children())
        elif method == 'hasAttribute':
            code += self._js_elements[key].hasAttribute(random.choice(HTML_ATTR_GENERIC))
        elif method == 'hasChildNode':
            code += self._js_elements[key].hasChildNodes()
        elif method == 'insertBefore':
            if not self._js_elements[key].get_children():
                elem_name, add_code, html_type = self.__add__new_element()
                code += add_code
                code += "\t" + self._js_elements[key].appendChild(elem_name) + "\n"
            elem_name, add_code, html_type = self.__add__new_element()
            code += add_code
            code += self._js_elements[key].insertBefore(elem_name, random.choice(self._js_elements[key].get_children()))
        elif method == 'normalize':
            code += self._js_elements[key].normalize()
        elif method == 'removeAttribute':
            if not self._js_elements[key].attributes:
                code += self._js_elements[key].setAttribute(random.choice(HTML_ATTR_GENERIC),
                                                            random.choice(FuzzValues.INTERESTING_VALUES))
            else:
                code += self._js_elements[key].removeAttribute(random.choice(self._js_elements[key].attributes.keys()))
        elif method == 'removeChild':
            if not self._js_elements[key].get_children():
                elem_name, add_code, html_type = self.__add__new_element()
                code += add_code
                code += self._js_elements[key].appendChild(elem_name)
            else:
                code += self._js_elements[key].removeChild(random.choice(self._js_elements[key].get_children()))
        elif method == 'replaceChild':
            if not self._js_elements[key].get_children():
                elem_name, add_code, html_type = self.__add__new_element()
                code += add_code
                code += self._js_elements[key].appendChild(elem_name)
            else:
                elem_name, add_code, html_type = self.__add__new_element()
                code += add_code
                code += self._js_elements[key].replaceChild(elem_name,
                                                            random.choice(self._js_elements[key].get_children()))
        elif method == 'removeEventListener':
            if not self._js_elements[key].registered_events:
                event = random.choice(DomObjectTypes.DOM_EVENTS)
                self._occurring_events[event] += 1
                code += self._js_elements[key].addEventListener(event, event + "_handler")
            else:
                event = random.choice(self._js_elements[key].registered_events.keys())
                self._occurring_events[event] -= 1
                event = random.choice(self._js_elements[key].registered_events.keys())
                code += self._js_elements[key].removeEventListener(event,
                                                                   self._js_elements[key].registered_events[event])
        elif method == 'setAttribute':
            attr = random.choice(HTML_ATTR_GENERIC)
            if attr == 'style':
                val = ""
                for i in range(1, 50):
                    css = random.choice(CSS_STYLES)
                    val += css[0] + ": " + random.choice(css[1:]) + "; "
            else:
                val = random.choice(FuzzValues.INTERESTING_VALUES)
            code += self._js_elements[key].setAttribute(attr, val)
        elif method == 'REPLACE_EXIST_ELEMENT':
            elem_name, add_code, html_type = self.__add__new_element()
            code += add_code
            code += "\t" + key + " = " + elem_name + ";"
            self._js_elements[key] = self._js_elements[elem_name]
        elif method == 'MIX_REFERENCES':
            code += self._js_elements[key]
        elif method == 'className':
            code += self._js_elements[key].className() + " = \"" + random.choice(FuzzValues.STRINGS) + "\";"
        elif method == 'contentEditable':
            code += self._js_elements[key].contentEditable() + " = " + random.choice(FuzzValues.BOOL) + ";"
        elif method == 'dir':
            code += self._js_elements[key].dir() + " = \"" + random.choice(FuzzValues.TEXT_DIRECTION) + "\";"
        elif method == 'id':
            code += self._js_elements[key].id() + " = \"" + random.choice(FuzzValues.STRINGS) + "\";"
        elif method == 'innerHTML':
            code += self._js_elements[key].innerHtml() + " = \"" + random.choice(FuzzValues.STRINGS) + "\";"
        elif method == 'lang':
            code += self._js_elements[key].lang() + " = \"" + random.choice(FuzzValues.LANG_CODES) + "\";"
        elif method == 'scrollLeft':
            code += self._js_elements[key].scrollLeft() + " = \"" + random.choice(FuzzValues.INTS) + "\";"
        elif method == 'scrollTop':
            code += self._js_elements[key].scrollTop() + " = \"" + random.choice(FuzzValues.INTS) + "\";"
        elif method == 'style':
            value = random.choice(CSS_STYLES)
            if "-" in value[0]:
                pos = value[0].find("-")
                value[0] = value[0].replace("-", "")
                value[0] = value[0][0:pos-1] + value[0][pos].upper() + value[0][pos+1:]
            code += self._js_elements[key].style() + "." + value[0] + " = \"" + random.choice(value[1:]) + "\";"
        elif method == 'tabIndex':
            code += self._js_elements[key].tabIndex() + " = " + str(random.randint(-20, 20)) + ";"
        elif method == 'textContent':
            code += self._js_elements[key].textContent() + " = \"" + random.choice(FuzzValues.STRINGS) + "\";"
        elif method == 'title':
            code += self._js_elements[key].title() + " = \"" + random.choice(FuzzValues.STRINGS) + "\";"
        self._operations_count += 1
        if random.randint(1, 10000) < 50:
            code += "CollectGarbage();"
        return code

    def __build_array(self, length=0):
        array_id = "array_" + str(len(self._arrays.keys()))
        self._arrays[array_id] = []
        code = array_id + " = ["
        array_length = length if length != 0 else random.randint(1, len(self._js_elements.keys()) / 2)
        for i in range(array_length):
            element_to_add = random.choice(self._js_elements.keys())
            self._arrays[array_id].append(self._js_elements[element_to_add])
            code += element_to_add + ","
        code = code[:-1] + "];\n"
        return code

    def __create_for_loop(self):
        pass

    def __create_if_clause(self):
        pass

    def __concate_startup_list(self):
        code = ""
        for item in self._calls_in_startup[:-1]:
            if random.randint(0,10) < 5:
                code += item + "\n"
            else:
                code += "\t" + JsWindow.setTimeout(item, self.TIMEOUT)
        return code