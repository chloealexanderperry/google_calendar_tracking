# python utils
import argparse
from termcolor import colored
import collections
from tabulate import tabulate
from blessed import Terminal

# date utilities
from dateutil.parser import parse
from dateutil import tz

# this library
from calendar_automator.lib import get_calendars_info, setup_calendar, load_start_end, load_calendars_from_file
from calendar_automator.read import load_events


term = Terminal()
def customround(x, base=5):
    return base * round(x/base)

def split_project_task(task):
  """Assume format:
    project: task
    returns project, task
  """
  split = task.split(":", 1)

  if len(split) == 1:

    # return split[0].strip(), split[0].strip()
    return split[0].strip(), ""
  elif len(split) == 2:
    # project, task
    return split[0].strip(), split[1].strip()
  elif len(split) == 0:
    raise RuntimeError("empty string?")
  else:
    return split[0], ":".join(split[1:]).strip()

def compute_event_length(event, tzinfo):
  """Compute the number of hours for the duration of an event"""
  event_start = event['start']['dateTime'].replace(tzinfo=tzinfo)
  event_end = parse(event['end']['dateTime']).replace(tzinfo=tzinfo)
  dif = event_end - event_start
  minutes = dif.total_seconds()/60/60
  return minutes

def format_task(task):
  task = task.replace("[p0]", "")
  task = task.replace("[p1]", "")
  task = task.replace("[p2]", "")
  task = task.replace("[p3]", "")
  task = task.replace("[p4]", "")
  return task

def task_priority(task):
  if "[p0]" in task: return 0
  elif "[p1]" in task: return 1
  elif "[p2]" in task: return 2
  elif "[p3]" in task: return 3 
  elif "[p4]" in task: return 4
  else:return 1

def priority2name(x):
  return {
    1: "    Important &     Urgent",
    2: "    Important & Not Urgent",
    3: "Not Important & Urgent",
    4: "Not Important & Not Urgent",
  }[x]

def multitask_project(project, time, time_percent, total_time, fulltask2length, fulltask2task, fulltask_names, line_divider):
  lines = []
  line = [project, '', "%.2f" % time, "%2.f" % time_percent]
  lines.append(line_divider)
  lines.append(line)

  for indx, fulltask_name in enumerate(fulltask_names):
    task = format_task(fulltask2task[fulltask_name])
    if not task: continue
    time = fulltask2length[fulltask_name]
    time_percent = 100*(time/total_time)
    line = ['', f"{indx+1}. {task}",  "%.2f" % time, "%2.f" % time_percent]
    lines.append(line)
  return lines

def singletask_project(project, time, time_percent, fulltask2length, fulltask2task, fulltask_names, line_divider):
  # -----------------------
  # get task information
  # -----------------------
  fulltask_name = fulltask_names[0]
  indx = 1
  task = format_task(fulltask2task[fulltask_name])

  lines = [line_divider]
  line = [project, task, "%.2f" % time, "%2.f" % time_percent]
  lines.append(line)

  return lines

def calculate_time_per_task(events, raw_end, end, tzinfo, 
  scheduling_events=set(['deep-work', 'block', 'paper', 'unscheduled']),
  priority_percent_goals={
  1: 70, # "    Important &     Urgent"
  2: 10, # "    Important & Not Urgent"
  3: 10, # "Not Important & Urgent"
  4: 5,  # "Not Important & Not Urgent"
  }
  ):
  nevents = len(events)

  # stores total time for project
  project2length = collections.defaultdict(float)

  # stores total time for individual tasks
  fulltask2length = collections.defaultdict(float)

  # stores taskname --> project
  fulltask2project=collections.defaultdict(str)

  # stores taskname --> task
  fulltask2task=collections.defaultdict(str)

  # ======================================================
  # get time for all tasks
  # ======================================================
  for event in events:
    fulltask_name = event['summary'].lower()
    project, task = split_project_task(fulltask_name)
    if project in scheduling_events:
      fulltask_name = project = "unscheduled"

    fulltask2project[fulltask_name] = project
    fulltask2task[fulltask_name] = task

    length = compute_event_length(event, tzinfo)
    fulltask2length[fulltask_name] += length

  # ======================================================
  # get time assigned at project-level
  # ======================================================
  project2fulltasks = collections.defaultdict(list)
  for fulltask_name, length in fulltask2length.items():
    project = fulltask2project[fulltask_name]
    project2length[project] += length
    project2fulltasks[project].append(fulltask_name)

  total_time = sum(project2length.values())


  # ======================================================
  # Want to print :
  # Priority| Time | % Total Time
  # ======================================================
  # -----------------------
  # first get time used for each
  # -----------------------
  priority2length = collections.defaultdict(float)
  # total_priority_time = 0
  for fulltask_name, length in fulltask2length.items():
    if fulltask_name in scheduling_events: continue
    priority = task_priority(fulltask_name)
    priority2length[priority] += length


  total_priority_time = sum([v for k,v in priority2length.items() if k])
  # -----------------------
  # now print
  # -----------------------
  header = ["Priority","Time: %.2f" % total_priority_time, "Percent", "Goal"]
  lines = []
  for priority, time in priority2length.items():
    if not priority: continue
    name = priority2name(priority)
    time_percent = 100*(time/total_priority_time)
    line = [name, "%.2f" % time, "%2.f" % time_percent, priority_percent_goals[priority]]
    lines.append(line)


  print(term.olivedrab1("="*15 + " Scheduled Time Priority Distribtuon " + "="*15))
  print(tabulate(lines, headers=header, tablefmt="pretty"))
  




  # ======================================================
  # Want to print in a hierarchical manner:
  # Project| Task | Time | % Total Time
  # ======================================================
  header=["Project","Task", "Time: %.2f" % total_time, "Percent"]
  lines = [header]
  title_lengths = [len(x) for x in header]
  max_project_length = len(max(project2fulltasks.keys(), key=lambda x: len(x)))
  formatted_tasknames = [format_task(t) for t in fulltask2task.values()]
  max_task_length = len(max(formatted_tasknames, key=lambda x: len(x)))
  line_divider = ["-"*(max_project_length+1),
                  "-"*(max_task_length+3),
                  "-"*(title_lengths[2]+1),
                  "-"*(title_lengths[3]+1)]

  # -----------------------
  # create lines for table
  # -----------------------

  # first remove unscheduled and add it manually
  project = 'unscheduled'
  time = project2length[project]
  time_percent = 100*(time/total_time)
  project2fulltasks.pop(project, None)
  lines.extend(singletask_project(project, time, time_percent, fulltask2length, fulltask2task, [project], line_divider))

  # then add the rest
  for project, fulltask_names in project2fulltasks.items():
    time = project2length[project]
    time_percent = 100*(time/total_time)
    if len(fulltask_names) > 1:
      new_lines = multitask_project(project, time, total_time, time_percent, fulltask2length, fulltask2task, fulltask_names, line_divider)
    elif len(fulltask_names) == 1:
      new_lines = singletask_project(project, time, time_percent, fulltask2length, fulltask2task, fulltask_names, line_divider)
    else:
      raise NotImplementedError
    lines.extend(new_lines)
  print("\n")
  print(term.orangered("="*15 + " Task Time Distribtuon " + "="*15))
  print(tabulate(lines, tablefmt="pretty"))


def calculate_time_per_day(events,
    raw_end,
    end,
    tzinfo,
    to_skip='_block',
    target_events=['block', 'deep-work', 'paper'],
    round_base=.25,
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]):

  indx = -1
  days = set()
  target_events = set(target_events)

  time_per_day = collections.defaultdict(float)

  for event in events:
    eventname = event['summary'].strip()
    if not (eventname in target_events): continue


    # -----------------------
    # get the day information
    # -----------------------
    event_start = event['start']['dateTime'].replace(tzinfo=tzinfo)
    start_day = event_start.day
    start_month = event_start.month
    start_day_indx = event_start.weekday()
    day = "%s %d/%d" % (day_names[start_day_indx], start_month, start_day)

    hours = compute_event_length(event, tzinfo)
    time_per_day[day] += hours

  # import ipdb; ipdb.set_trace()
  if not time_per_day: return

  total_time = sum(time_per_day.values())
  # -----------------------
  # now print
  # -----------------------
  header = ["Day","Time: %.2f" % customround(total_time, round_base), "Percent", '']
  lines = []
  for day, time in time_per_day.items():
    rounded_time = customround(time, round_base)


    time_percent = 100*(time/total_time)
    blocks = "x"*int((1/round_base)*rounded_time)
    line = [day, "%.2f" % rounded_time, "%2.f" % time_percent, blocks]
    lines.append(line)

  print("\n")
  print(term.darkgoldenrod1("="*15 + " Unscheduled Daily Time Distribtuon " + "="*15))
  print(tabulate(lines, headers=header, tablefmt="pretty"))
  







def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--start", default=None, help="start time. format: month/day/year hour:minute, e.g. 5/20/2018 5:34. If nothing set, will use current time.")
    parser.add_argument("-e", "--end", default=None, help="end time. format: month/day/year hour:minute, e.g. 5/20/2018 5:34. If nothing set, will use end of current day.")
    parser.add_argument("-t", "--timezone", default="US/Eastern")
    parser.add_argument("-v", "--verbose", action='store_true')
    args = parser.parse_args()

    tzinfo = tz.gettz(args.timezone)


    service = setup_calendar()
    calendar_list = load_calendars_from_file()
    calendars = get_calendars_info(service, calendar_list)

    # ======================================================
    # parse start and end dates into objects
    # ======================================================
    start, end = load_start_end(args.start, args.end, tzinfo)

    # ======================================================
    # get all events within that time-frame
    # ======================================================
    all_events = load_events(service, calendars, start, end, tzinfo) # per calendar
    combined_events = [] # combined across calendars
    for calendar in calendars:
      combined_events += all_events[calendar]


    # turn start dateTime into a datetime object for all events
    for event in combined_events:
      event['start']['dateTime'] = parse(event['start']['dateTime'])
    combined_events = sorted(combined_events, key = lambda x: x['start']['dateTime'])


    calculate_time_per_task(combined_events, args.end, end, tzinfo)
    calculate_time_per_day(combined_events,args.end,end,tzinfo)



if __name__ == '__main__':
  main()