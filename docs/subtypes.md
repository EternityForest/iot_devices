# Data subtypes for IoT devices

## Development

Don't define any types here you don't have an immediate use for.  If you to describe data in a way that isn't covered by units of measure,
just use a URI type name like "foo.blah.myawesometype".   This file should not be 758 pages long. We want to use as few different primitives as possible.

## string

### color

A CSS style hex color starting with #

## Numeric

### trigger

This is a simple counter used to represent something like button presses, rocket ignition, or things like that.
It must take integer values.  Note that it may at any point wrap around or go backwards if a sender uses smaller int variables
or loses track.

Should the number go backwards, it should be interpreted as one single event.  Incrementing numbers of more than one can be assumed to represent multiple events.  If exact numbers of events are important, use 64 bit counters that will not overflow in relevant timescales.


A device must not send any kind of default value for this if it does not actually have an event to send. The count
should begin at 1 for the first event.


The main purpose of this is so that devices can declare a pushbutton-like input.

### timetrigger

This is a timestamp used for the same purpose as trigger.  Note that within the data itself, unix times are preferred
because data points already have the monotonic metadata, but any kind of timestamp in floating point seconds may be used.
Only deltas should be examined here, the real point is just to use it as a simple trigger.

### light_fade_duration

Represents a setting that affects the duration of a light fade.

### bool

0 or 1.

### tristate

0,1 or -1 to indicate unset/no output/passive/no data yet/etc.


## Object

### event

This is a list containing [eventName, timestamp, data] where data may be any type.  As with timetrigger, the timestamp may be
in any format the device wants to send, but should be expressed in floating point seconds.

### textmessage

An object with the following, used for representing a stream of chat messages.

text: the message as a string
priority: debug, error, info, warning, critical
timestamp: float

### gnss

This is an object with at minimum lat, lon, time, and alt stored as floats.