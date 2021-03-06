import re
import sys
from graphviz import Graph

### Read and parse a crochet pattern file.
### Create a connected graphlike structure to traverse
### Output a Chart (oneday)

### Pattern rules are simple ATM
### - round or grid of rows on first line
### - one line for each row
### - stitches are named and repeat groups are in * groups


stitch_pattern = re.compile(r'(?:(?:([0-9]*)([slchdtrk]{2,3}))( \+)?)+')
whitespace = re.compile(r'^\s+$')

flatten = lambda l: [item for sublist in l for item in sublist]

class StitchPattern(object):
    """ Holds the parsed pattern of Stitches 
    """
    def __init__(self, pattern_type, parsed_pattern, name):
        self.pattern = parsed_pattern
        self.pattern_type = pattern_type
        self.start_stitches = 1 if self.pattern_type == 'round' else int(self.pattern_type.split()[1])
        self.expand_row_helper = {}
        self.name = name

    def expand(self):
        """ return fully expanded rows of all stitches
        """
        return [self.expand_row(i) for i in range(len(self.pattern))]

    def count_stitches(self, rownum):
        """ count stitches in each row
            - deal with chains, slips and skips
        """
        stitch_list = self.expand_row(rownum)
        count = 0
        chcount = 0
        for st in stitch_list:
            if st == 'sl' or st == 'sk':
				# if slip or skip then reset chcount
                chcount = 0
            elif st == 'ch':
                chcount += 1
                # inc count by 1 for every 3 ch stitches
                if chcount >= 3:
                    count += 1
            else:
                chcount = 0 # not a chain or a slip or skip so reset chcount
                count += 1
        return count

    def expand_stitchgroup(self, stitchgroup):
        " return flat list of all stitches in a stitchgroup "
        return flatten([self.expand_stitch(s) for s in stitchgroup])

    def expand_stitch(self, stitch):
        """ return list of individual stitches.
            special case chain stitches of length 3
        """
        if stitch == ('ch', 3):
            return ['ch3']
        st, ct = stitch
        return [st for x in range(ct)]

    def expand_row(self, rownum):
        " return flat list of all stitches in the row "
        # cache already expanded rows to avoid reworking them
        if rownum not in self.expand_row_helper:
            self.expand_row_helper[rownum] = self._expand_row(rownum)
        return self.expand_row_helper[rownum]

    def _expand_row(self, rownum):
        """ expand stitch list for all stitchgroups in a row 
            - return flat list of stitches
        """
        # is this the first stitch in the row
        if rownum == 0:
            prev_stitch_num = self.start_stitches
        else:
            prev_stitch_num = self.count_stitches(rownum - 1)
        #
        row = self.pattern[rownum]
        if len(row) == 1:
            return flatten([self.expand_stitchgroup(s) for s in row[0]])
        else:
            stitch_list = flatten([self.expand_stitchgroup(s) for s in row[0]])
            row_len_left = prev_stitch_num - len(row[0])
            repeat_idx = 0
            while row_len_left > 0:
                stitch_list.extend(self.expand_stitchgroup(row[1][repeat_idx]))
                row_len_left -= 1
                repeat_idx += 1
                if repeat_idx == len(row[1]):
                    repeat_idx = 0
            stitch_list.extend(flatten([self.expand_stitchgroup(s) for s in row[2]]))
            return stitch_list

	# called by viz
    def stitch_map(self):
        " "
        self.stitch_num_id = 1
        return self.stitch_map_row_accuum(0, [self.foundation_row_map()])

    def stitch_map_row_accuum(self, rownum, map_so_far):
        " "
	# are we done yet
        if rownum == len(self.pattern):
            return map_so_far
        #
        row = self.pattern[rownum]
        prev_row = map_so_far[-1]
        prev_row_idx = 0
        new_map_row = []
        # special case row witha single stitch
        short_row = 0 if len(row) > 1 else 1
        for i in range(len(row[0]) - short_row):
            # expand one stitchgroup at a time gathering stitches 
            stitches = self.expand_stitchgroup(row[0][i])
            for j in range(len(stitches)):
                if stitches[j] == 'sk':
                    prev_row_idx += 1
                    continue
                if len(new_map_row) > 0:
                    prev = new_map_row[-1]
                else:
                    prev = prev_row[-1]
                if stitches[j] == 'ch' or stitches[j] == 'sl':
                    # chain and slip stitches are not connected to a prev row
                    bottom = None
                else:
                    bottom = prev_row[prev_row_idx]
                    # store the stitch along with prev and sitch it is stitched into
                new_map_row.append(Connected_stitch(self.get_stitch_id(), stitches[j], prev, bottom))
            prev_row_idx += 1 
        if len(row) == 1:
            # special case single stitch rows
            last_stitchgroup = row[0][-1]
        else:
            #! todo fix me only handles one stitch after repeat
            last_stitchgroup = row[2][0]
            # repeat time
            #! used_count doesn't deal with skips in the postamble
            prev_row_stop = len(prev_row) - len(row[2])
            repeat_idx = 0
            while prev_row_idx < prev_row_stop:
                stitches = self.expand_stitchgroup(row[1][repeat_idx])
                for j in range(len(stitches)):
                    if stitches[j] == 'sk':
                        prev_row_idx += 1
                        continue
                    if len(new_map_row) > 0:
                        prev = new_map_row[-1]
                    else:
                        prev = prev_row[-1]
                    if stitches[j] == 'ch' or stitches[j] == 'sl':
                        bottom = None
                    else:
                        bottom = prev_row[prev_row_idx]
                    new_map_row.append(Connected_stitch(self.get_stitch_id(), stitches[j], prev, bottom))
                prev_row_idx += 1 
                repeat_idx += 1
                if repeat_idx >= len(row[1]):
                    repeat_idx = 0
        #! todo fix this - only handles case where ending is one stitch
        stitch = last_stitchgroup[0][0]
        new_map_row.append(Connected_stitch(self.get_stitch_id(),stitch, new_map_row[-1], prev_row[-1]))
        return self.stitch_map_row_accuum(rownum + 1, map_so_far + [new_map_row])

	# called by stitch_map (viz)
    def foundation_row_map(self):
        """ Initial stitch in the pattern.
            return magic loop for 'rounds' or nothing 
        """
        if self.pattern_type == 'round':
            return [Connected_stitch(self.get_stitch_id(), 'magic loop')]

    def get_stitch_id(self):
        retval = self.stitch_num_id
        self.stitch_num_id += 1
        return retval

    def viz(self):
        """ Build a dotmap for graphviz 
            but also constructs the connected_stitch structures
        """
        flatmap = flatten(self.stitch_map())
        if self.pattern_type == 'round':
            dot = Graph(engine="twopi", graph_attr={'root': 'a1', 'overlap': 'false'}, node_attr={'shape': 'circle', 'margin': '0.00001 0.0001'}, format="png", name=self.name)
        else:
            dot = Graph(format="png", name=self.name)
        # first pass nodes
        for stitch in flatmap:
            dot.node("a" + str(stitch.id), str(stitch.stitch))
        # second pass edges
        for stitch in flatmap:
            if(stitch.prev):
                dot.edge("a" + str(stitch.id), "a" + str(stitch.prev.id))
            if(stitch.bottom):
                dot.edge("a" + str(stitch.id), "a" + str(stitch.bottom.id))
        dot.render(view=True)


class Connected_stitch(object):
    """ Each Stitch points to previous
         and bottom 
        - which is the location of connection on previous row
    """
    def __init__(self, idnum, stitch, prev=None, bottom=None):
        self.id = idnum
        self.stitch = stitch
        self.prev = prev
        self.bottom = bottom

def parse_stitch(stitch):
    """ For each stitch in the pattern file 
        - ?
    """
    result = []
    for match in stitch_pattern.finditer(stitch):
        num = int(match.group(1) or 1)
        result.append((match.group(2), num))
    return result


def parse_pattern(filename):
    """ extract the lines from file and
        return list of parsed stitches
    """
    with open(filename, 'r') as f:
        lines = f.readlines()
        pattern_type = lines[0].strip()
        name = filename.split('.')[0]
        # for each line parse all the stitches
        #  - split on * and for each , separated stitch
        parsed_stitches = [[[parse_stitch(sg.strip()) for sg in tris.split(',') if len(sg.strip()) > 0] for tris in l.strip().split('*')] for l in lines[1:]]
        return (name, pattern_type, parsed_stitches)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg1 = sys.argv[1]
    else:
        arg1 = 'example_pattern.txt'
    # parse the written pattern
    name, ptype, rows = parse_pattern(arg1)
    # construct a StitchPattern from the parsed stitches
    sp = StitchPattern(ptype, rows, name)
    # report
    print sp.expand()
    for row in rows:
        print "row:"
        if len(row) == 1:
            for stitch in row[0][:-1]:
                print "\tstitch:", stitch
            print "\tjoin:", row[0][-1]
        else:
            print "\tstart:"
            for stitch in row[0]:
                print "\t\tstitch:", stitch
            print "\trepeat:"
            for stitch in row[1]:
                print "\t\tstitch:", stitch
            print "\tjoin:"
            for stitch in row[-1]:
                print "\t\tstitch:", stitch
    # Visualize it (also makes structure)
    sp.viz()
