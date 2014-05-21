#!/usr/bin/env python3

from os import listdir, path, walk
import re
from fnmatch import fnmatch
import pickle
import sys


FILENAME = 'ds.dot'
HLIST_PICKLE = 'hlist.pickle'
MAP_PICKLE = 'mapper.pickle'
KEY_PICKLE = 'keywords.pickle'


def alias_gen():
    if(path.isfile(MAP_PICKLE)):
        with open(MAP_PICKLE, 'rb') as f:
            mapper = pickle.load(f)
    else:
        mapper = dict()
    mapper = dict()
    hlist = hlist_gen()
    for file in hlist:
        with open(file) as f:
            lines = [line.strip() for line in f]
            index = 0
            while index < len(lines):
                sline = lines[index]
                #remove comment and re-strip spaces
                sline = sline.split("/*")[0].strip()
                if "typedef" in sline and "enum" not in sline and "#include" not in sline:
                    endchar = sline[len(sline)-1]
                    if endchar == ';':
                        splitted = sline.strip(';').split()
                        if len(splitted) != 3: #typedef sth sth sth
                            if "struct" in sline or "union" in sline:
                                removelist = ['typedef', '*', 'struct',
                                              'union']
                                cleanedlist = [left for left in splitted if
                                              left not in removelist]
                                add_mapper(cleanedlist[1], cleanedlist[0],
                                           mapper)
                        else: # typedef sth sth
                            filterlist = ['void', 'char', 'long', 'int']
                            standard_type = False
                            for filter in filterlist:
                                if filter in splitted[1]:
                                    standard_type = True
                                    break;
                            if not standard_type:
                                add_mapper(splitted[2], splitted[1], mapper)
                        index += 1
                    elif is_struct_def(sline):
                        original = keyword_from_str(sline)
                        if original == "":
                            #not alias, original def omit:
                            index += 1
                            continue
                        left_brace = sline.count('{')
                        right_brace = sline.count('}')
                        while left_brace > right_brace:
                            index += 1
                            sline = lines[index]
                            left_brace += sline.count('{')
                            right_brace += sline.count('}')
                        alias = sline.split('}')[-1].strip().split(';')[0].strip()
                        if alias != original:
                            add_mapper(alias, original, mapper)
                        index += 1
                    else:
                        index += 1
                else:
                    index += 1
    #save mapper to pickle
    with open(MAP_PICKLE, 'wb') as f:
        pickle.dump(mapper, f)
    return mapper


def keyword_from_str(str):
    return str[str.find("struct")+len("struct")+1:str.find("{")].strip()


def is_struct_def(str):
    str = str.strip()
    return "struct" in str and "{" in str and str[0] != "*" and str[0:2] != "/*"


def keywords_builder(rebuild = False):
    '''
    Build the keyword list contains all struct we define in the dir,
    recursively
    '''
    if not rebuild:
        if(path.isfile(KEY_PICKLE)):
            with open(KEY_PICKLE, 'rb') as f:
                return pickle.load(f)
    hlist = hlist_gen()
    keywords = set()
    for file in hlist:
        with open(file) as f:
            for lines in f:
                if is_struct_def(lines):
                    keyword = keyword_from_str(lines)
                    if keyword is not "":
                        keywords.add(keyword)
    with open(KEY_PICKLE, 'wb') as f:
        pickle.dump(keywords, f)
    return keywords


def relation_builder():
    '''
    Read all .h files in a dir recursively. Find all struct defs. Build a
    relation mapping between these structs and all other structs they refer to
    '''
    mapper = alias_gen()
    hlist = hlist_gen()
    keywords = keywords_builder(rebuild = True)
    pattern = '(struct\s*)?(?P<type>[a-zA-Z0-9_]+)\**\s*\**\s*(?P<var>[a-zA-Z0-9_]+)(\[\S+\])?;\s*(?P<comment>\/\*.*\*?\/?)*'
    regex = re.compile(pattern)
    relation_mapper = dict()
    for file in hlist:
        with open(file) as f:
            lines = [line.strip() for line in f]
            index = 0
            while index < len(lines):
                sline = lines[index]
                if is_struct_def(sline):
                    keyword = keyword_from_str(sline)
                    #if "typedef" in sline:
                    #struct def starts
                    left_braces = sline.count('{')
                    right_braces = sline.count('}')
                    members = []
                    while left_braces > right_braces:
                        index += 1
                        sline = lines[index]
                        left_braces += sline.count('{')
                        right_braces += sline.count('}')
                        m = regex.search(sline)
                        if m:
                            type = m.group('type')
                            var = m.group('var')
                            type = find_origin(type, mapper)
                            if type in keywords:
                                members.append((type, var))
                    if keyword == "":
                        keyword = sline[sline.find("{")+2:sline.find(";")].strip()
                    if keyword != "":
                        for member in members:
                            if member[0] != keyword:
                                add_relation(keyword,
                                            member[0],
                                            member[1],
                                            relation_mapper)
                    if keyword not in relation_mapper.keys():
                        relation_mapper[keyword] = []
                    #else:
                    #    print(sline)
                    index += 1
                else:
                    index += 1
    return relation_mapper


def find_origin(keyword, mapper):
    while keyword in mapper.keys():
        keyword = mapper[keyword]
    return keyword


def add_relation(struct_name, struct_member_type, struct_member,
                 relation_mapper):
    if struct_name not in relation_mapper.keys():
        relation_mapper[struct_name] = []
    relation_mapper[struct_name].append((struct_member_type, struct_member))


def add_mapper(key, value, mapper):
    #if key in mapper.keys() and mapper[key] != value:
    #    print("current value for key " +
    #          key +  " is " +
    #          mapper[key])
    #    print("trying to add new value: " +
    #          value)
    assert key not in mapper.keys() or mapper[key] == value
    mapper[key] = value



def hlist_gen(rebuild = False):
    if not rebuild:
        if(path.isfile(HLIST_PICKLE)):
            with open(HLIST_PICKLE, 'rb') as pickle_f:
                return pickle.load(pickle_f)
    dot_hs = []
    for paths, subdirs, files in walk(sys.argv[1]):
        for file in files:
            if fnmatch(file, "*.h") and file[0] != '.':
                dot_hs.append(path.join(paths, file))
    with open(HLIST_PICKLE, 'wb') as pickle_f:
        pickle.dump(dot_hs, pickle_f)
    return dot_hs


def write_header():
    with open(FILENAME, 'w') as f:
        f.write('digraph g {\ngraph [\nrankdir= \"LR\"\n];\n')
        f.write('node [\nfontsize = \"16\"\nshape = \"ellipse\"\n];\n')
        f.write('edge [\n];\n')


def write_dot_file():
    write_header()
    relation_mapper = relation_builder()
    labels = [label for label in relation_mapper.keys()]
    alias_mapper = alias_gen()
    with open(FILENAME, 'a') as f:
        for labels_index in range(len(labels)):
            f.write('\"node' + str(labels_index) + "\" [\n")
            f.write("label = \" <f0> " + labels[labels_index])
            members = relation_mapper[labels[labels_index]]
            for i in range(len(members)):
                f.write(' | <f' + str(i+1) + '>' + members[i][1] + ' ')
            f.write('\"\n')
            f.write('shape = \"record\"\n];\n')
        id = 0
        for node, edges in relation_mapper.items():
        #edges is a list of (type var) tuple
            for edge in edges:
                type, var = edge
                if type not in labels:
                    #type = alias_mapper[type]
                    type = find_origin(type, alias_mapper)
                    print(type)
                    assert type in labels
                f.write("\"node" + str(labels.index(node)) + "\":" + "f" + str(edges.index(edge) + 1) +
                        " -> \"node" + str(labels.index(type))  + "\": f0 [\n id = " + str(id) + "\n];\n")
                id += 1
        f.write("}")


if __name__ == "__main__":
    write_dot_file()
    #relation_builder()
    #alias_gen()
