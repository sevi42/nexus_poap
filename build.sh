#!/bin/sh


for f in `ls *.py`
do
echo "Building :" $f
f=93120TX_poap.py ; cat $f | sed '/^#md5sum/d' > $f.md5 ; sed -i "s/^#md5sum=.*/#md5sum=\"$(md5sum $f.md5 | sed 's/ .*//')\"/" $f
done
echo "Done"