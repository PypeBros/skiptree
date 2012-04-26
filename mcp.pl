#!/usr/bin/perl
use Socket;
#use Sys::Hostname;


$port=8086;     # first port we will try
$lastport=8100; # port we'll stop at.

socket(LISTEN, PF_INET, SOCK_STREAM, getprotobyname('tcp')) or die 'socket(t)';
setsockopt(LISTEN, SOL_SOCKET, SO_REUSEADDR, 1);

$myname = `uname -n`;
chomp $myname;
$myaddr=gethostbyname($myname);
$myaddr=inet_aton($myaddr) if length $myaddr>4;
$TADDR =inet_ntoa($myaddr);
print STDERR "$myname = $TADDR\n";
$la = sockaddr_in($port,$myaddr);

# --- bind them ---
# both sockets need to be bound so that source port of advertisments is $port
# and that we listen for TCP connections on the same $port.
bind(LISTEN, $la) or die "SOMEONE STPPED ON MCP CHANNEL. EOL\n";
listen LISTEN, 2048;

welcome();
print STDERR "BOUND AND LISTENING\n";
open LOG, ">MCP.now" or die "you want logging on MCP.now, don't you?";
select LOG; $|=1; select STDOUT;
# --- file name ---
# we are only allowed 32 bytes per advertisement message, including IP:port
# information that is displayed on the DS. We make sure that only the filename
# (and not the complete path) is advertised and we shorten it (keeping last 
# characters) so that it fit the 32-bytes constraint.


my @ready=("$TADDR:8080");
my @pending=();
my $status='FREE';
# --- the loop ---
my $FH;
while(1) {
  # -- if there's a pending connection, we end up here.
  eval {
    $FH=undef;
    ($remport,  $remaddr) = sockaddr_in(accept($FH,LISTEN));
    # -- we want to ensure that only the DS can request the file.
    #    this is not public offer.
  };
  print STDERR "connection received from ".inet_ntoa($remaddr)."\n";
  last if !defined $FH;
  eval {
    my $who=<$FH>;
    my @info=();
    if ($who=~/TRON/) {
      print $FH "END Of LINE\n";
      close $FH;
      foreach(@pending) {
	print $_ "KILL \r\n";
	close $_;
      }
      close LISTEN;
      exit 0;
    }
    chomp $who;
    while ($d=<$FH>) {
      last if !defined $d;
      push @info, $d;
      print LOG "$who - $d";
      last if $d=~/^#_# /;
    }
    if ( $status eq 'FREE' && $info[-1]=~/ READY/){
      dojoin($ready[0]);
    } elsif ($status eq 'BUSY' && $info[-1]=~/ READY/) {
    enqueue();
    } elsif ($status eq 'BUSY' && $info[-1]=~/ CONNECTED/) {
      dequeue();
    } else {
      print STDERR "unexpected $who $info[-1] in state $status\n";
      noop();
    }
  };
}
close LISTEN;

exit 0;

sub dojoin {
  my ($ip,$port)=split /:/,$_[0];
  print STDERR "JOIN GRANTED ($ip:$port)\n";
  print LOG "JOIN GRANTED ($ip:$port)\n";
  print $FH "TYPE 2;$port;$ip;\r\n";
  close $FH;
  $status='BUSY';
}

sub enqueue {
  push @pending,$FH;
  undef $FH;
}

sub dequeue {
  print STDERR "CONNECTION ACKNOWLEDGED $FH\n";
  print LOG "CONNECTION ACKNOWLEDGED $FH\n";
  print $FH "TYPE 0;1\r\n";
  close $FH;
  if (@pending) {
    $FH=shift @pending;
    dojoin($ready[0]);
  } else {
    print STDERR "ALL THE PROGRAMS JOINED THE GRID. EOL\n";
    $status='FREE';
  }
}

sub noop {
  print $FH "WAIT\r\n";
  close $FH;
}

sub welcome {
print STDERR <<___
................,,,:,,=====~~::~~~~~~====~~~~~~~::~~====~:,:,,,..,.............,
................,,:,:~=====~~~~~~~~~~====~~~~~:~~:~~~=====~,,,,..,.......,......
................,,:,:~===~:::::~:~~~~====~~~~~~~::::~====~~:::,.................
................,::::===~~~~~~~~~~~~~=====~~~~~~::~~~~~==~~:,,.....,............
................,,:~~=~===~~~~::~~~~=======~~~~~~~~~~=====~,,,,....,,,.....,....
.........,,......,,~~===~:::~~~~~~~~=======~~~~~:~~:::==+=~,,,......,,,.........
........,,.....,.,,:==~=+=~~~~~~~~~~======~~~~~~:~~~~==+:==:,,......,,,.........
.......,,,,,.....,,:~:===~~~~~::::~~======~~~:::~~~~~====:=:,,...,,,,,,,.....,..
......,,,,,,,,,,,,,~=+===~~~:~::~~~~======~~~~~::~~~~~==++=~,,,,,,,,,,:,,.,...,.
......,:,,,,,,,,,,,~=+===~~~~~~~~~~~=======~~~~~~~~~~~===+=~,::::,,::,:,,,,.....
...,,,,:,,,,,:,:,,:======~~:~~~~::::~~~~~~~~:::~~~~~~~~==++=::::~::::::::,,,,,..
...,,:::::,::::~::======~~~~::::::::~~~~~~~::::::::~~~~=====~:::::,:::::::,,,,..
,.,,:,:,:::::::::~==+===~~::::::::~~~~==~=~~~::::::::~~===+==:::::::::~~~::,,,,.
.,,,:~::~::::::~~~=++==~~:~~~~~~~~~~=======~~~~~~~~~::~===++=~~:~~~~::~:~::,,,,,
,,,::~~:::::::~==~=++===~~~~~~~~~~~~=======~~~~~~~~~~~~===++=~~~~===~::::~~:,,,,
,,,:~~::::~=~~===~==+===~~~~~~~~~~~~=======~~~~~~~~~~~~=====+~==~~~~~::::~~~,,,,
,,:~~~~:~~====++=~=+===~~~~~~~~~~~~~========~~~~~~~~~~~~==+==~~========~~~~::,,,
,:::~~=~~~++++====+====~~~~~~~~~~~~~=======~~~~~~~~~~~~~====+==~~~~~===~~::~::,:
::::::~~~~=++==+=+=====~~~~~~~~~~~~~=======~~~~~~~~~~~~===========~~=~~~::::::::
:,:::::~~~~==~=+~=++=====~~~~~~~~~~~=======~~~~~~~~~~=====+++=====+===~~::::~:::
:~:,:::~==:~~~~===+++====~~~~~~~~~~~~=====~~~~~~~~~~=====++++==++==~~=~~::::~:::
,::,,,:~==~===~~~====++====~~~~~~~~~~====~~~~~~~~~~~===+++++==~~~==~~~:::::::~~:
::::,,,,~~~===~:~~~==++++===~~~~~~~~~=====~~~~~~~~====+++===~~~~~+==~::,,::::~:~
::::,,,,,,:~===~~~~~~===++===~~~~~~~~====~~~~~~~~===+++===~~~~~=+===~::,,,::::~~
=::,,,,:,,:::~~+++=~:~~===++===~~~~~~~===~~~~~~~===++==~~~~~==+==~~::,,,,:::::==
=~===,,,,:,::~~~~~+?+=~~~~==++==~~~~~~===~~~~~~==++==~~~~=+?+~~~~~::::,~,,===~==
=========::::~~~~~:~:~?+=~~~~====~~~~~==~~~~~~====~~~~=+?~~~:~~~~~::::==========
==~==========:~:::::~~:~==?+~~~===~~:~==~~:~====~:~+?~~~~~::::::~~==========~===
==~==========~~:::,,~:::::~===+~:=+=~~~=~~~=+~:=?~~~=~~~::::::::~:==============
___
  ;
}
