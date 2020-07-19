#!/usr/bin/env python
import sublime, sublime_plugin, sublime_api
import os, re, json, math, textwrap, sys
import Papyrus.papyrus_test as _test

suggestions_master = {}
functions_master = {} #functions_master["native"][class_name][#] = function (variable: +extended_class_name+)

# suggestions will not show up if the line contains any of these keywords
no_suggestions_with_keyword = [
    "function", "property", "scriptname", "state"
]

suggestion_lists = {}

# make functions suggestions based on the parent we're pulling from: <parent>.
# make context menu papyrus syntax only?
# and add a "show source" option in context menu:
# you right click a word and have the option to view source for certain words (i.e. the script exists)

def plugin_loaded():
    global suggestions_master
    global functions_master
    global suggestion_lists

    settings = sublime.load_settings("Papyrus.sublime-settings")
    package_path = os.path.dirname(os.path.realpath(__file__))

    for extentions in settings.get("script_extenders"):
        for name in extentions:
            # loads the classes/events into the plugin
            path = package_path + extentions[name]

            suggestions_master[name] = {}
            suggestions_master[name]["events"] = {}
            suggestions_master[name]["classes"] = []

            with open(path, "r") as fp:
                try:
                    data = json.load(fp)

                    for evs in data["events"]:
                        for eventname, params in evs.items():
                            suggestions_master[name]["events"][eventname] = params

                    for cs in data["classes"]:
                        suggestions_master[name]["classes"].append(cs)
                finally:
                    fp.close()

            # loads the functions into the plugin
            if os.path.exists(package_path + "\\language\\functions\\{}".format(name)):
                functions_master[name] = {}
                path = package_path + "\\language\\functions\\{}".format(name)

                for funcfp in os.listdir(path):
                    _path = os.path.join(path, funcfp)
                    _name = re.sub(r"(?i)\.(\w+)", "", funcfp)
                    functions_master[name][_name] = []

                    with open(_path, "r") as fp:
                        try:
                            data = json.load(fp)

                            if len(data["extends"]) > 0:
                                functions_master[name][_name].append("+{}+".format(data["extends"]))

                            for func in data["functions"]:
                                functions_master[name][_name].append(func)
                        finally:
                            fp.close()

    suggestion_lists = {
        "default": get_suggestion_list("default", ["statement", "function", "declaration", "specialkeyword"]),
        "all_events": get_suggestion_list(["native", "skse"], "events"),
        "all_types": get_suggestion_list(["native", "skse"], "classes"),
    }

    for ext in suggestions_master.keys():
        suggestion_lists[ext] = get_suggestion_list(ext)
        suggestion_lists[ext + "_types"] = get_suggestion_list(ext, "classes")
        suggestion_lists[ext + "_events"] = get_suggestion_list(ext, "events")

def _get_functions(pull_from = "native", class_name = "form"):
    _functions = []

    for cla, func in functions_master[pull_from].items():
        if cla.lower() == class_name.lower():
            is_native = (pull_from.lower() == "native")

            for _func in func:
                ex_match = re.search(r"(?<=\+)(\w+)(?=\+)", _func, re.IGNORECASE)
                func_name = re.search(r"(?i)\w+(?=\()", _func)
                func_params = re.search(r"(?i)(?<=\()(.*)(?=\))", _func)

                if ex_match:
                    _functions += _get_functions(pull_from, ex_match.group())
                else:
                    if func_name:
                        func_name = func_name.group()
                    else:
                        func_name = "None"

                    if func_params:
                        func_params = func_params.group()
                    else:
                        func_params = "None"

                    if is_native:
                        desc = "Method"
                    else:
                        desc = "Method*"

                    # what if instead of making the params an option to select, you hover the function for params?

                    _functions.append(format_completion(func_name, desc, func_name))
                    _functions.append(format_completion(func_name, desc + "+", func_name, func_params))
                    #_functions.append(format_completion(func_name.lower(), desc, func_name))
                    #_functions.append(format_completion(func_name.lower(), desc + "+", func_name, func_params))

    return _functions

#functions_master["native"][class_name][#] = function (variable: +extended_class_name+)
def get_function_suggest_list(pull_from = "native", class_name = "form"):
    suggestions = []
    suggestions_dict = {}
    extends = "None"

    if pull_from == "_defined_":
        pull_from = "native"
        #print("parent: " + get_parent(parent))
        #this might need to be a different function all together as it needs View access, and Point
        #check and see if it was defined in the scope
        #if not, check global scope (basically remove all text between function-endfunction, etc, and then search)

    suggestions = _get_functions(pull_from, class_name)
    suggestions.sort()

    for s in suggestions:
        prefix = s[0][0]
        suggestions_dict.setdefault(prefix, []).append(s)

    return suggestions_dict

# self.get_suggestion_list("default", ["statement", "function", "declaration", "specialkeyword"])
# self.get_suggestion_list("native", ["events"])
# self.get_suggestion_list("skse", ["classes"])
# self.get_suggestion_list(["native", "skse"], ["classes"])
def get_suggestion_list(pull_from = ["native"], suggest_what = ["events", "classes"]):
    suggestions = []
    suggestions_dict = {}
    pull = []
    what = []

    if type(pull_from) == str:
        pull.append(pull_from.lower())
    elif type(pull_from) == list:
        pull = pull_from
    else:
        pull = ["native"]

    if type(suggest_what) == str:
        what.append(suggest_what.lower())
    elif type(suggest_what) == list:
        what = suggest_what
    else:
        what = ["events", "classes"]

    def_types = ['int', 'float', 'bool', 'string']
    statement_list = ['if', 'while']
    functions_list = ['function', 'event', 'state', 'property']
    keywords_list = ['ScriptName', 'Import']

    def_types.sort()
    statement_list.sort()
    functions_list.sort()
    keywords_list.sort()

    if pull[0].lower() == "default":
        for sug in suggestions_master.keys():
            for tp in suggestions_master[sug]["classes"]:
                def_types.append(tp)

        for w in what:
            if w.lower() == "statement":
                for tag in statement_list:
                    suggestions.append(format_completion(tag, 'Statement'))
                    suggestions.append(format_completion(tag.capitalize(), 'Statement'))
            elif w.lower() == "function":
                for tag in functions_list:
                    suggestions.append(format_completion(tag, 'Function'))
                    suggestions.append(format_completion(tag.capitalize(), 'Function'))
            elif w.lower() == "declaration":
                for tag in def_types:
                    suggestions.append(format_completion(tag, 'Declaration', tag))
                    suggestions.append(format_completion(tag.lower(), 'Declaration', tag))
            elif w.lower() == "specialkeyword":
                for tag in keywords_list:
                    suggestions.append(format_completion(tag, "Keyword", tag))
                    suggestions.append(format_completion(tag.lower(), "Keyword", tag))

        for s in suggestions:
            prefix = s[0][0]
            suggestions_dict.setdefault(prefix, []).append(s)

        return suggestions_dict
    else:
        for p in pull:
            for w in what:
                for t in suggestions_master[p][w]:
                    if w == "events":
                        if p != "native":
                            tag = "*Event"
                        else:
                            tag = "Event"

                        suggestions.append(format_completion(t, tag, t, suggestions_master[p][w][t]))
                        suggestions.append(format_completion(t.lower(), tag, t, suggestions_master[p][w][t]))
                    elif w == "classes":
                        if p != "native":
                            tag = "*Class"
                        else:
                            tag = "Class"

                        suggestions.append(format_completion(t, tag, t))
                        suggestions.append(format_completion(t.lower(), tag, t))

        for s in suggestions:
            prefix = s[0][0]
            suggestions_dict.setdefault(prefix, []).append(s)

        return suggestions_dict

def get_parent(keyword):
    for parent in suggestions_master.keys():
        foundclass = [typename for typename in suggestions_master[parent]["classes"] if typename.lower() == keyword.lower()]
        foundevent = [eventname for eventname in suggestions_master[parent]["events"] if eventname.lower() == keyword.lower()]

        if foundclass or foundevent:
            return parent
        else:
            # we're looking for a function
            # skse functions havent been added yet lol, need to make their json's before skse will show up here
            # no point in looking for the parent in the suggestions_master classes because if no functions are tied
            # to it, there would be no functions to suggest
            if [func_parent for func_parent in functions_master[parent] if func_parent.lower() == keyword.lower()]:
                return parent

    return None

def format_completion(tag, tag_type, *args):
    org_tag = tag
    tag_generic_close = '\nEnd' + org_tag.capitalize()
    tag_contents = ''
    org_tag_type = tag_type
    tag_type = tag_type.replace("*", "").replace("+", "")

    if len(tag) >= 23:
        tag = tag[:18] + '…'

    tag_intro = (tag + '\t' + org_tag_type)
    function_no_open = ["state", "property", "event"]

    if tag_type.lower() == "event":
        if len(args) > 0:
            tag_contents = args[0] + '()\n\t'
            tag_contents = (args[0] + '(' + args[1] + ')\n\t')
    elif tag_type.lower() == "declaration":
        tag_contents = (args[0] + ' Property $0 Auto')
    elif tag_type.lower() == "function":
        if org_tag.lower() in function_no_open:
            tag_contents = (org_tag.title() + ' $0' + tag_generic_close)
        else:
            tag_contents = (org_tag.title() + ' $0()' + tag_generic_close)
    elif tag_type.lower() == "class":
            tag_contents = (args[0] + " $0")
    elif tag_type.lower() == "keyword":
        tag_contents = args[0] + " $0"
    elif tag_type.lower() == "method":
        if len(args) > 1:
            org_tag = args[0]
            params = args[1]
        else:
            org_tag = args[0]
            params = "$0"

        if org_tag_type.find("+") != -1:
            tag_contents = org_tag + "(" + params + ")"
        else:
            tag_contents = org_tag + "($0)"
    else:
        tag_contents = (org_tag.title() + ' $0\n\t') + tag_generic_close

    return (tag_intro, tag_contents)

def line_contains_keyword(view, point, keyword):
    return (keyword.lower() in view.substr(view.line(point)).strip().rstrip().lower().split(' '))

def get_word_infront(view, point):
    try:
        line = view.substr(view.line(point)).strip().rstrip().lower().split(' ')
        ind = 0

        for word in line:
            if word == view.substr(view.word(point)).lower():
                break
            ind += 1

        return line[ind - 1]
    except:
        return None

def get_word_after(view, point):
    try:
        line = view.substr(view.line(point)).strip().rstrip().lower().split(' ')
        ind = 0

        for word in line:
            if word == view.substr(view.word(point + 1)).lower():
                break
            ind += 1

        return line[ind]
    except:
        return None

def get_nth_word_in_line(view, point, n):
    n -= 1
    line = view.substr(view.line(point)).strip().rstrip().lower().split(' ')
    
    if n >= len(line):
        return None
    
    return line[n]

def after_dot_before_anything_else(view, point):
    pos = view.rowcol(point - 1)
    suggest = [False, ""]

    if view.substr(sublime.Region(point, point - 1)) == ".":
        line = view.substr(view.line(point)).lower()

        for m in re.finditer(r"(?i)([a-z0-9]+[^\(|\)])(?=\.)", line):
            start_pos = view.text_point(pos[0], m.start())
            end_pos = view.text_point(pos[0], m.start() + len(m.group()))
            parent = view.substr(sublime.Region(start_pos, end_pos))

            if end_pos == point - 1:
                strs_in_line = re.search(r"(?<=\")(.*)(?=\")", line, re.IGNORECASE)

                if strs_in_line:
                    if strs_in_line.group().find(parent.lower()) != -1:
                        suggest = [False, parent]
                        continue

                if re.search(r"(self|parent)", parent.lower(), re.IGNORECASE):
                    suggest = [False, parent]

                suggest = [True, parent]
                break

    return suggest

class PapyrusCompletions(sublime_plugin.EventListener):
    def __init__(self):
        self.settings = sublime.load_settings("Papyrus.sublime-settings")
        self.package_path = sublime.packages_path()
        self.phantom_view = None

    def IS_PAPYRUS_SCRIPT(self):
        return (re.sub(r"(?i)(?:(\w+/)|(\.(\w+-\w+)))", "", sublime.active_window().active_view().settings().get('syntax').lower()) == "papyrus")

    def on_query_completions(self, view, prefix, locations):
        if not self.IS_PAPYRUS_SCRIPT():
            return []

        return self.get_completions(view, prefix, locations)

    def on_hover(self, view, point, hover_zone):
        htext = view.substr(view.word(point)).strip().rstrip()
        parent = get_parent(htext)

        if not self.IS_PAPYRUS_SCRIPT() or len(htext) == 0 or (parent == None):
            return

        if hover_zone == sublime.HOVER_TEXT:
            if parent != "native":
                self.show_popup(view, point, "Added by: " + parent.upper())

    def show_popup(self, view, point, text):
        width = 2 * math.floor(view.em_width()) * len(text)
        sublime_api.view_show_popup(view.view_id, view.word(point).begin(), text, sublime.HIDE_ON_MOUSE_MOVE_AWAY, width, 40, None, None)

    def get_completions(self, view, prefix, locations):
        is_event = line_contains_keyword(view, locations[0], "event")
        is_import = line_contains_keyword(view, locations[0], "import")
        is_scriptname = line_contains_keyword(view, locations[0], "scriptname")
        is_pulling_method = after_dot_before_anything_else(view, locations[0])
        will_show = True

        if not is_event and not is_import and not is_scriptname and not is_pulling_method[0]:
            for hide in no_suggestions_with_keyword:
                if line_contains_keyword(view, locations[0], hide):
                    will_show = False
                    break

        if not will_show or not is_pulling_method[0]:
            return ([], sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

        completion_list = []
        flags = 0

        if is_event:
            if len(prefix.strip()) == 0:
                prefix = "O"

            completion_list = suggestion_lists["all_events"].get(prefix[0], [])
            flags = sublime.INHIBIT_WORD_COMPLETIONS
        elif is_import:
            if len(prefix.strip()) == 0:
                prefix = "A"

            completion_list = suggestion_lists["all_types"].get(prefix[0], [])
            flags = sublime.INHIBIT_WORD_COMPLETIONS
        elif is_scriptname:
            if get_word_infront(view, locations[0]) == "extends":
                if len(prefix.strip()) == 0:
                    prefix = "A"

                completion_list = suggestion_lists["all_types"].get(prefix[0], [])
                flags = sublime.INHIBIT_WORD_COMPLETIONS
            else:
                flags = sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS
        elif is_pulling_method[0] and len(is_pulling_method[1]) > 0:
            sugs = []
            parent = get_parent(is_pulling_method[1])

            if parent == None:
                parent = "_defined_"
            else:
                parent = parent.lower()

            for x in list(get_function_suggest_list(parent, is_pulling_method[1]).values()):
                for y in x:
                    sugs.append((y[0], y[1]))

            sugs.sort()

            completion_list = sugs
            flags = sublime.INHIBIT_WORD_COMPLETIONS
        else:
            if len(prefix.strip()) == 0:
                prefix = "A"

            completion_list = suggestion_lists["default"].get(prefix[0], [])
            
        completion_list = [(pair[0], pair[1]) for pair in completion_list]
        return (completion_list, flags)

    def create_phantom(self, view, point):
        self.phantom_view = view
        stylesheet = '''
            <style>
                div.error {
                    padding-left: 0.7rem;
                    margin: 0 0 0.2rem;
                }
                div.error span.message {
                    padding-right: 0.7rem;
                }
                div.error a {
                    text-decoration: inherit;
                    padding: 0.35rem 0.7rem 0.45rem 0.8rem;
                    position: relative;
                    border-radius: 0 0.2rem 0.2rem 0;
                    font-weight: bold;
                }
            </style>
        '''
        reg = sublime.Region(view.line(point).b)

        view.erase_phantoms("skse-hover")
        view.add_phantom ("skse-hover", reg,
            ('<body id=inline-error>' + stylesheet + 
                '<div class="error">' +
                '<span class="message">Added by SKSE</span>' +
                '<a href=hide>' + chr(0x00D7) + '</a></div>' +
                '</body>'), sublime.LAYOUT_INLINE, on_navigate=self.hide_phantom)

    def hide_phantom(self, view):
        self.phantom_view.erase_phantoms("skse-hover")
        self.phantom_view = None

class papyrus_save(sublime_plugin.ApplicationCommand):
    def run(self):
        sublime.load_settings("Papyrus-Theme.sublime-settings")
        settings = sublime.load_settings("Papyrus.sublime-settings")
        scripts_directory = os.path.join(str(sublime_api.settings_get(settings.settings_id, "skyrim_directory")), "Data\\Source\\Scripts")

        view = sublime.active_window().active_view()
        scriptname = "None"

        try:
            scriptname = view.substr(view.line(0)).strip().rstrip().split(' ')[1]
        except:
            sublime.error_message("You lack a ScriptName!")
            return

        view.settings().set('default_dir', scripts_directory)
        view.assign_syntax('Packages/Papyrus/Papyrus.sublime-syntax')
        view.set_name(scriptname + ".psc")

        path = os.path.join(scripts_directory, scriptname + ".psc")
        view.run_command('save')
        print(path)

class papyrus_new(sublime_plugin.WindowCommand):
    def run(self):
        v = self.window.new_file()
        
        scripts_directory = os.path.join(str(sublime_api.settings_get(sublime.load_settings("Papyrus.sublime-settings").settings_id, "skyrim_directory")), "Data\\Source\\Scripts\\")
        print(scripts_directory)

        v.settings().set('default_dir', scripts_directory)
        v.assign_syntax('Packages/Papyrus/Papyrus.sublime-syntax')

        template = (
            """
            ScriptName $0
            """
        )
        v.run_command("insert_snippet", {"contents": textwrap.dedent(template).lstrip()})

class pretty_code_papyrus(sublime_plugin.TextCommand):
    def run(self, edit):
        self.window = sublime.active_window()
        self.view = self.window.active_view()
        self.settings = sublime.load_settings("Papyrus.sublime-settings")
        self.language = re.sub(r"(?i)(?:(\w+/)|(\.(\w+-\w+)))", "", self.view.settings().get('syntax').lower())
        self.regex = self.load_regex_from_file()

        #{ "command": "set_setting", "args": {"setting": "tab_size", "value": 4}, "caption": "Tab Width: 4", "checkbox": true },
        #{ "command": "expand_tabs", "caption": "Convert Indentation to Spaces", "args": {"set_translate_tabs": true} },
        #{ "command": "unexpand_tabs", "caption": "Convert Indentation to Tabs", "args": {"set_translate_tabs": true} }
        self.window.run_command("set_setting", {"setting": "tab_size", "value": 4})
        self.window.run_command("unexpand_tabs", {"set_translate_tabs": True})
        #replace(r"( {2})", r"\t") <- with 2 being whatever the tab_size WAS BEFORE CHANGE

        line_regions = self.view.split_by_newlines(sublime.Region(0, self.view.size()))

        for region in line_regions:
            line_text = self.view.substr(self.view.line(region))

            for word in self.view.substr(region).split(' '):
                for reg in self.regex:
                    match = re.search(reg, word, re.IGNORECASE)

                    if match:
                        matched = self.fold_hex(self.view, region, match.group())
                        line_text = line_text.replace(matched, self.format_match(matched, reg))

            sublime_api.view_replace(self.view.view_id, edit.edit_token, self.view.line(region), line_text)
        sublime.status_message("Pretty Print – Papyrus")

    def fold_hex(self, view, line_region, match):
        if bool(re.search(r"(?i)([a-f0-9]{8})", match)) and False:
            loc = view.find(match[:4], line_region.begin(), sublime.IGNORECASE)
            view.fold(loc)

        return match

    def format_match(self, match, reg):
        funcs = (['upper', 'lower', 'capitalize'])

        # format placeholders
        re_match = re.sub(r"(?i){match}", match, self.regex[reg])

        # apply functions
        for func in funcs:
            param_reg = r"(?i)(?<=" + func + r"\()(.*?)(?=\))"
            param = re.search(param_reg, re_match, re.IGNORECASE)

            if param:
                x = param.group(1)
                re_match = re_match.replace("{}({})".format(func, match), eval("x.{}()".format(func)))

        return re_match

    def load_regex_from_file(self):
        regex_path = os.path.dirname(os.path.realpath(__file__)) + '\\' + str(sublime_api.settings_get(self.settings.settings_id, "pretty_code_regex"))
        rules = {}

        if self.language == "papyrus":
            with open(regex_path, "r") as fp:
                data = json.load(fp)

            for lang_regex in data['papyrus']:
                for rule, rep in lang_regex.items():
                    rules[rule] = rep

            fp.close()

        if len(rules) == 0:
            return None
        else:
            return rules

# for smart capitalization:
# read through entire sublime dictionary looking for words
# and also read through the current file for words
# when running through each word, go letter by letter until a word is found