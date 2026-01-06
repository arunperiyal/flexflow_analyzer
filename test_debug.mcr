#!MC 1410
$!VarSet |datafile| = '/media/arunperiyal/Works/projects/flexflow_manager/CS4SG1U1/binary/riser.1050.plt'
$!VarSet |outfile| = '/tmp/test_out.dat'

# Load dataset
$!READDATASET  '|datafile|' 
  READDATAOPTION = NEW
  RESETSTYLE = YES

# Write to file
$!WRITEDATA SET '|outfile|'
  ZONELIST = [1]
  VARLIST = [1-3]
  INCLUDETEXT = NO
  INCLUDEGEOM = NO
  BINARY = NO

$!QUIT
