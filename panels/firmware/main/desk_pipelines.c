/* The House panel's pipelines (plan.md M21) from the hub's answer: each "pipeline"
 * screen is one running (or just finished) run as a job graph, at most two; the
 * "pipelines" screen is the idle card. Kept apart from desk.c, which is long enough. */

#include "desk_pipelines.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void text(char *to, size_t size, const cJSON *from)
{
    snprintf(to, size, "%s", cJSON_IsString(from) ? from->valuestring : "");
}

static int number(const cJSON *from, int otherwise)
{
    return cJSON_IsNumber(from) ? from->valueint : otherwise;
}

static uint32_t hex(const cJSON *from)
{
    if (!cJSON_IsString(from) || from->valuestring[0] != '#') {
        return 0x8f80ff;
    }
    return (uint32_t)strtoul(from->valuestring + 1, NULL, 16);
}

#define FIELD(name) cJSON_GetObjectItem(screen, name)

void desk_parse_run(const cJSON *screen, desk_pipeline_t *pipeline)
{
    if (!cJSON_IsTrue(FIELD("present")) || pipeline->count >= DESK_PIPELINE_RUNS) {
        return;
    }
    pipeline->present = true;
    pipeline->stale = pipeline->stale || cJSON_IsTrue(FIELD("stale"));
    desk_run_t *run = &pipeline->runs[pipeline->count++];
    memset(run, 0, sizeof *run);
    text(run->title, sizeof run->title, FIELD("title"));
    text(run->number, sizeof run->number, FIELD("number"));
    text(run->position, sizeof run->position, FIELD("position"));
    text(run->state, sizeof run->state, FIELD("state"));
    run->colour = hex(FIELD("colour"));
    text(run->big, sizeof run->big, FIELD("big"));
    const cJSON *since = FIELD("since");
    run->since = cJSON_IsNumber(since) ? (int64_t)since->valuedouble : 0;
    text(run->first, sizeof run->first, FIELD("first"));
    text(run->second, sizeof run->second, FIELD("second"));
    text(run->commit, sizeof run->commit, FIELD("commit"));
    text(run->meta, sizeof run->meta, FIELD("meta"));
    run->columns = number(FIELD("columns"), 1);
    const cJSON *job;
    cJSON_ArrayForEach(job, FIELD("jobs"))
    {
        if (run->job_count == DESK_PIPELINE_JOBS) {
            break;
        }
        typeof(run->jobs[0]) *j = &run->jobs[run->job_count++];
        text(j->name, sizeof j->name, cJSON_GetObjectItem(job, "name"));
        j->column = (uint8_t)number(cJSON_GetObjectItem(job, "column"), 0);
        j->row = (uint8_t)number(cJSON_GetObjectItem(job, "row"), 0);
        j->count = (uint8_t)number(cJSON_GetObjectItem(job, "count"), 1);
        text(j->state, sizeof j->state, cJSON_GetObjectItem(job, "state"));
        text(j->time, sizeof j->time, cJSON_GetObjectItem(job, "time"));
        j->progress = (int16_t)number(cJSON_GetObjectItem(job, "progress"), 0);
    }
    const cJSON *edge;
    cJSON_ArrayForEach(edge, FIELD("edges"))
    {
        int from = number(cJSON_GetArrayItem(edge, 0), -1), to = number(cJSON_GetArrayItem(edge, 1), -1);
        if (run->edge_count < DESK_PIPELINE_EDGES && from >= 0 && to >= 0 && from < run->job_count &&
            to < run->job_count) {
            run->edges[run->edge_count][0] = (uint8_t)from;
            run->edges[run->edge_count++][1] = (uint8_t)to;
        }
    }
}

void desk_parse_pipelines(const cJSON *screen, desk_pipelines_t *pipelines)
{
    pipelines->present = cJSON_IsTrue(FIELD("present"));
    pipelines->stale = cJSON_IsTrue(FIELD("stale"));
    const cJSON *repo;
    cJSON_ArrayForEach(repo, FIELD("repos"))
    {
        if (pipelines->count == 3) {
            break;
        }
        typeof(pipelines->repos[0]) *r = &pipelines->repos[pipelines->count++];
        text(r->name, sizeof r->name, cJSON_GetObjectItem(repo, "name"));
        text(r->line, sizeof r->line, cJSON_GetObjectItem(repo, "line"));
        r->colour = hex(cJSON_GetObjectItem(repo, "colour"));
        const cJSON *bar;
        cJSON_ArrayForEach(bar, cJSON_GetObjectItem(repo, "bars"))
        {
            if (r->bar_count == 10) {
                break;
            }
            r->bars[r->bar_count].height = (int16_t)number(cJSON_GetObjectItem(bar, "height"), 0);
            r->bars[r->bar_count++].ok = cJSON_IsTrue(cJSON_GetObjectItem(bar, "ok"));
        }
    }
}
