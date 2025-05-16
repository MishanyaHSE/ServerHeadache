import pandas as pd
import numpy as np
from fastapi import HTTPException
from sqlalchemy import select, and_

from app.models import Note


def convert_to_native(df_grouped):
    if isinstance(df_grouped.columns, pd.MultiIndex):
        df_grouped.columns = ['_'.join(col).strip() for col in df_grouped.columns.values]
    return df_grouped.reset_index().applymap(
        lambda x: x.item() if isinstance(x, np.generic) else x
    )


async def create_statistics(date_start, date_end, user_id, db):
    query = (
        select(Note)
        .where(
            and_(
                Note.user_id == user_id,
                Note.date >= date_start,
                Note.date <= date_end
            )
        )
        .order_by(Note.date)
    )
    notes = (await db.execute(query)).scalars().all()
    if len(notes) == 0:
        raise HTTPException(status_code=404, detail="Notes not found")
    result = {}

    data = [note.__dict__ for note in notes]
    df = pd.DataFrame(data)

    total_days = (date_end - date_start).days + 1
    # 1 пункт
    percent = round((len(notes) / total_days * 100))
    result["fill_percentage"] = percent
    # 2 пункт
    pain_days = df[df['is_headache']]
    days_with_pain = len(pain_days)
    days_without_pain = len(notes) - days_with_pain
    result["headache_days"] = {'without_pain': days_without_pain, 'with_pain': days_with_pain}
    # 3 пункт
    df['headache_hour'] = df['headache_time'].apply(lambda x: x.hour if pd.notnull(x) and pd.notnull(x.hour) else None)
    condition = [
        (df['headache_hour'].between(23, 23) | df['headache_hour'].between(0, 5)),
        df['headache_hour'].between(6, 11),
        df['headache_hour'].between(12, 17),
        df['headache_hour'].between(18, 22),
        df['headache_hour'].isna()
    ]
    choices = ['night', 'morning', 'afternoon', 'evening', 'na']
    df['time_category'] = np.select(condition, choices, 'na')
    time_stats = df[df['is_headache']].groupby('time_category').size()
    time_result = {cat: time_stats[cat] for cat in choices if cat in time_stats}
    result['time_stats'] = {
        cat: int(time_stats.get(cat, 0))
        for cat in choices if cat != 'na'
    }
    # 4 пункт
    top_durations = ((df[df['is_headache']]
                      .groupby('duration')
                      .size()
                      .sort_values(ascending=False)
                      .reset_index(name='count'))
                     .to_dict('records'))
    result['top_durations'] = top_durations
    # 5 пункт
    mean_intensity = round(df[df['is_headache']]['intensity'].mean(), 1) if not df[df['is_headache']].empty else 0
    result['mean_intensity'] = mean_intensity
    # 6 пункт
    triggers_series = (
        df[df['is_headache'] & df['triggers'].notnull() & df['triggers'].astype(str).ne('[]')].explode('triggers')[
            'triggers'].dropna().str.strip())
    top_triggers_dict = triggers_series.value_counts().head(3).reset_index(name='count').rename(
        columns={'index': 'trigger'}).to_dict()
    top_triggers = [{'name': top_triggers_dict['triggers'][i], 'count': top_triggers_dict['count'][i]} for i in
                    range(len(top_triggers_dict['count'].keys()))]
    counted_triggers = [i['name'] for i in top_triggers]
    count = 0
    for note in notes:
        if note.triggers is not None:
            for trigger in note.triggers:
                if trigger not in counted_triggers:
                    count += 1
    top_triggers.append({'name': 'Остальные', 'count': count})

    result['top_triggers'] = top_triggers
    return result