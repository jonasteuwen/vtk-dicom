"""
Generate a C++ DICOM dictionary from a text file.

This program will read a text file generated from the DICOM data
element regsistry table (DICOM Chapter 6 part 6) and will generate
a hash table that can be used for dictionary lookups.

Usage: python makedict.py nemadict.txt > vtkDICOMDictHash.cxx
Usage: python makedict.py --header nemadict.txt > vtkDICOMDictHash.h

The option "--private" can be added to create a private dictionary.
"""

import sys
import math

header = \
"""/*=========================================================================
This is an automatically generated file.  Include errata for any changes.
=========================================================================*/"""

printheader = False
privatedict = False
filename = None
for arg in sys.argv[1:]:
  if arg == "--header":
    printheader = True
  elif arg[0:10] == "--private=":
    privatedict = arg[10:]
  elif arg[0] != '-' and filename == None:
    filename = arg
  else:
    sys.stderr.write(
      """usage: python makedict.py nemadict.txt > vtkDICOMDictHash.cxx
      python makedict.py --header nemadict.txt > vtkDICOMDictHash.h\n""")
    sys.exit(1)

# the hash table, in PYTHON
htsize = 4096

# collect private dictionaries
privatelines = {}

# read the file in one go
f = open(filename, 'r')
lines = f.readlines()
f.close()

# look for repeating groups and repeat them
i = 0
rg = []
while i < len(lines):
  tag = lines[i].strip()
  try:
    g, e = tag[1:10].split(',')
  except ValueError:
    sys.stderr.write("exception: %s\n" % (tag))
  if g == "60xx" or g == "50xx":
    rg.extend(lines[i:i+6])
    i = i + 6
  elif rg:
    nb = []
    for j in range(1,16):
      k = 0
      m = len(rg)
      while k < m:
        g, e = rg[k][1:10].split(',')
        nb.append("(%s%02X,%s)\n" % (g[0:2], 2*j, e))
        nb.append("%s %d\n" % (rg[k+1].strip(), j+1))
        nb.append("%s%d\n" % (rg[k+2].strip(), j+1))
        nb.append(rg[k+3])
        nb.append(rg[k+4])
        nb.append(rg[k+5])
        k = k + 6
    lines = lines[0:i] + nb + lines[i:]
    i += len(nb)
    rg = []
  else:
    # check for and filter out the private tags
    private = False
    try:
      private = ((int(g[3]) & 0x1) != 0)
    except:
      pass
    if private:
      creator = lines[i + 5].strip()
      try:
        privatelines[creator] += lines[i:i+6]
      except KeyError:
        privatelines[creator] = lines[i:i+6]
    i = i + 6

def hashstring(s):
  """Compute a string hash based on the function "djb2".
  Use at most 64 characters.
  """
  h = 5381
  s = s[0:64]
  for c in s:
    h = ((h << 5) + h + ord(c)) & 0xffffffff
  return h

def makedict(lines, creator="DICOM"):
  # the tables that will be created
  enum_list = []
  element_list = []
  entry_list = []

  # a set to keep track of all VM strings encountered
  vms = {}

  htsize = 4096
  if privatedict:
    htsize = int(len(lines)/6)
    if htsize == 0:
      htsize = 1

  ht = [None]*htsize
  ht2 = [None]*htsize

  # iterate through all elements in the table
  j = 0
  i = 0
  n = len(lines)
  while i < n:
    try:
      tag = lines[i].encode('ascii').strip()
      i = i + 1
      name = lines[i].encode('ascii').strip()
      i = i + 1
      key = lines[i].encode('ascii').strip()
      i = i + 1
      vr = lines[i].encode('ascii').strip()
      i = i + 1
      vm = lines[i].encode('ascii').strip()
      i = i + 1
      ret = lines[i].encode('ascii').strip()
      i = i + 1
    except:
      sys.stderr.write("non-ascii character encountered on line %d\n" % (i,))
      raise TypeError

    # replace "Unknown" and "?" with ""
    if name in ("Unknown", "Internal", "?"):
      name = ""
    if key in ("Unknown", "Internal", "?"):
      key = ""

    # replace "US or SS" with "XS"
    if vr in ("US or SS", "SS or US", "xs"):
      vr = "XS"

    # replace "OB or OW" with "OX"
    if vr in ("OB or OW", "OW or OB", "ox"):
      vr = "OX"

    # replace "see note" with "XX"
    if vr in ("", "see note", "See Note"):
      vr = "XX"

    # replace mixed short with "OW"
    if len(vr) > 2:
      if vr.find("OW") >= 0:
        vr = "OW"
        vm = "1"
      if vr.find("OB") >= 0:
        vr = "OB"
        vm = "1"

    # replace 'RET' with 1 or 0
    if ret and not privatedict:
      if not printheader:
        ret = {"RET":"1","DICONDE":"2","DICOS":"3"}[ret]
      elif ret == "RET":
        ret = "1"
    else:
      ret = "0"

    # prefix vm with 'M', change '-' to 'T', change 'n' to 'N'
    vm = 'M' + vm.split(' ')[0].replace('-', 'T').replace('n', 'N')
    # add to the set of VMs
    vms[vm] = True

    # this is debug info: make sure no keys are over 63 chars,
    # which is the maximum id length in the C++ standard
    if len(key) > 63:
      print "XXXXXX", key
      sys.exit(1)

    # get the group, element
    g, e = tag[1:10].split(',')

    # make sure g, e are hexadecimal integers
    try:
      gi = int(g, 16)
      ei = int(e, 16)
    except:
      # replace 'x' (which means any digit) with zero
      #print "XXXXXX %s %s" % (tag, key)
      g = g.replace('xx','00')
      e = e.replace('xxxx','0000')
      e = e.replace('xxx','000')
      e = e.replace('xx','00')
      e = e.replace('x','1')
      gi = int(g, 16)
      ei = int(e, 16)

    if key or privatedict:
      enum_list.append(
        ("%-39s = 0x%s%s, // %s %-5s %s" % (key, g, e, vr, vm, ret)).strip())

      element_list.append(
        "{ 0x%s, 0x%s, %s, VR::%s, VM::%s, \"%s\" }," % (g, e, ret, vr, vm, key))

      # create a 16-bit hash from group, element
      h = ((gi ^ (gi >> 6)) ^ (ei ^ (ei >> 6)))

      # create a string hash
      hkey = hashstring(key)

      # build the hash tables
      h = (h % htsize)
      if ht[h] == None:
        ht[h] = []
      h2 = (hkey % htsize)
      if ht2[h2] == None:
        ht2[h2] = []

      # build the index table
      ht[h].append(j)
      ht[h].append(ei)

      ht2[h2].append(j)
      ht2[h2].append((hkey//htsize) & 0xffff)
      j = j + 1

  # debug: print all VM's that were found
  #print vms.keys()

  # debug: print statistics about the hash table
  #print maxl, minl, k0, k4
  return enum_list, element_list, ht, ht2

# write the output file
def printhead(enum_dict, classname):
  print header
  print
  print "#ifndef %s_h" % (classname,)
  print "#define %s_h" % (classname,)
  print
  if not privatedict:
    print "//! Tag values defined in the DICOM standard"
    print "namespace DC"
    print "{"
    print "enum EnumType {"
    for enum_list in enum_dict.values():
      # eliminate the "," for the last enum item
      m = len(enum_list)
      if m:
         enum_list[m-1] = enum_list[m-1].replace(", //", "  //")
      for l in enum_list:
        print l
    print "};"
    print "} // end namespace DC"
  else:
    print "// This must be included before the initializer is declared."
    print "#include \"vtkDICOMDictionary.h\""
    print
    print "// Initializer to add dict when header included."
    print "struct VTK_DICOM_EXPORT %sInitializer" % (classname,)
    print "{"
    print "  %sInitializer();" % (classname,)
    print "  ~%sInitializer();" % (classname,)
    print "};"
    print
    print "static %sInitializer %sInitializerInstance;" % (classname,classname);
  print
  print "#endif /* %s_h */" % (classname,)

def printbody(entry_dict, classname):
  print header
  print
  print "#include \"vtkDICOMDictionary.h\""
  print "#include \"%s.h\"" % (classname,)
  print

  print "namespace {"
  print
  print "typedef vtkDICOMVR VR;"
  print "typedef vtkDICOMVM VM;"
  print "typedef vtkDICOMDictEntry::Entry DictEntry;"

  ns = ""
  if not privatedict:
    ns = "vtkDICOMDictionary::"

  dn = 0
  for name, (entry_list, tag_table, key_table) in entry_dict.items():
    dn = dn + 1
    ds = ""
    print
    if len(entry_dict) > 1:
      ds = "%03d" % (dn,)
      print "// ----- %s -----" % (name,)
      print
    print "const DictEntry Dict%sContents[] = {" % (ds,)
    for l in entry_list:
      print l
    print "};"
    for table,tagorkey in [(tag_table,"Tag"),(key_table,"Key")]:
      print
      print "const unsigned short Dict%s%sHashTable[] = {" % (ds,tagorkey)
      i = 0
      j = len(table) + 1
      for l in table:
        if l is None:
          print "%5d," % (len(table),),
          i = i + 1
          if i % 10 == 0:
            print
        else:
          print "%5d," % (j,),
          i = i + 1
          if i % 10 == 0:
            print
          j = j + len(l) + 1
      print "%5d," % (0,),
      i = i + 1
      if i % 10 == 0:
        print
      for l in table:
        if not (l is None):
          print "%5d," % (len(l)/2,),
          i = i + 1
          if i % 10 == 0:
            print
          for e in l:
            print "%5d," % (e,),
            i = i + 1
            if i % 10 == 0:
              print
      if i % 10 != 0:
        print
      print "};"

    if not privatedict:
      print
      print "} // end anonymous namespace"

    print
    if len(entry_dict) > 1:
      ds = "%03d" % (dn,)
    print "vtkDICOMDictionary::Dict %sDict%sData = {" % (ns,ds)
    print "\"%s\"," % (name,)
    print "%d," % (len(tag_table),)
    print "%d," % (len(entry_list),)
    print "Dict%sTagHashTable," % (ds,)
    print "Dict%sKeyHashTable," % (ds,)
    print "Dict%sContents" % (ds,)
    print "};"

  if privatedict:
    print
    print "vtkDICOMDictionary::Dict *PrivateDictData[] = {"
    dn = 0
    for item in entry_dict.items():
      dn = dn + 1
      print "&Dict%03dData," % (dn,),
      if dn % 5 == 0:
        print
    print "NULL"
    print "};"
    print
    print "} // end anonymous namespace"
    print
    print "static unsigned int %sInitializerCounter;" % (classname,)
    print
    print "%sInitializer::%sInitializer()" % (classname,classname)
    print "{"
    print "  if (%sInitializerCounter++ == 0)" % (classname,)
    print "  {"
    print "    for (vtkDICOMDictionary::Dict **dp = PrivateDictData; *dp != NULL; dp++)"
    print "    {"
    print "      vtkDICOMDictionary::AddPrivateDictionary(*dp);"
    print "    }"
    print "  }"
    print "}"
    print
    print "%sInitializer::~%sInitializer()" % (classname,classname)
    print "{"
    print "  if (--%sInitializerCounter == 0)" % (classname,)
    print "  {"
    print "    for (vtkDICOMDictionary::Dict **dp = PrivateDictData; *dp != NULL; dp++)"
    print "    {"
    print "      vtkDICOMDictionary::RemovePrivateDictionary((*dp)->Name);"
    print "    }"
    print "  }"
    print "}"

if privatedict:
  enum_dict = {}
  entry_dict = {}

  for name, lines in privatelines.items():
    enum_list, entry_list, tag_table, key_table = makedict(lines, name)
    enum_dict[name] = enum_list
    entry_dict[name] = (entry_list, tag_table, key_table)

  if printheader:
    printhead(enum_dict, privatedict)
  else:
    printbody(entry_dict, privatedict)

else:
  enum_list, entry_list, tag_table, key_table = makedict(lines)

  classname = "vtkDICOMDictHash"

  if printheader:
    printhead({"DICOM" : enum_list}, classname)
    print "// VTK-HeaderTest-Exclude: %s.h" % (classname,)
  else:
    printbody({"DICOM" : (entry_list, tag_table, key_table)}, classname)

# informative: these names represent a range of tag values
""" keys with ranges
(0020,3100 to 31FF) SourceImageIDs
(0028,04x0) RowsForNthOrderCoefficients
(0028,04x1) ColumnsForNthOrderCoefficients
(0028,04x2) CoefficientCoding
(0028,04x3) CoefficientCodingPointers
(0028,08x0) CodeLabel
(0028,08x2) NumberOfTables
(0028,08x3) CodeTableLocation
(0028,08x4) BitsForCodeWord
(0028,08x8) ImageDataLocation
(1000,xxx0) EscapeTriplet
(1000,xxx1) RunLengthTriplet
(1000,xxx2) HuffmanTableSize
(1000,xxx3) HuffmanTableTriplet
(1000,xxx4) ShiftTableSize
(1000,xxx5) ShiftTableTriplet
(1010,xxxx) ZonalMap
"""
