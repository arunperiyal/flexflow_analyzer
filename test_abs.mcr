#!MC 1410
$!READDATASET  '/media/arunperiyal/Works/projects/flexflow_manager/CS4SG1U1/binary/riser.1050.plt' 
  READDATAOPTION = NEW
  RESETSTYLE = YES
$!WRITEDATA set "/tmp/test_output.dat"
  ZONELIST = [1]
  VARLIST = [1-2]
  INCLUDETEXT = NO
  INCLUDEGEOM = NO
$!QUIT
