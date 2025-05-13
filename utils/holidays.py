from datetime import datetime


def get_holidays(year: int):
    holidays = [
        {"label": datetime(year, 1, 1).strftime('%Y-%m-%d'),
         "value": "ទិវាចូលឆ្នាំសាកល"},
        {"label": datetime(year, 2, 7).strftime('%Y-%m-%d'),
         "value": "ទិវាជ័យជម្នះលើរបបប្រល័យពូជសាសន៍"},
        {"label": datetime(year, 3, 8).strftime('%Y-%m-%d'),
         "value": "ទិវាអន្តរជាតិនារី"},
        {"label": datetime(year, 5, 1).strftime('%Y-%m-%d'),
         "value": "ទិវាពលកម្មអន្តរជាតិ"},
        {"label": datetime(year, 4, 14).strftime('%Y-%m-%d'),
         "value": "ពិធីបុណ្យចូលឆ្នាំថ្មីប្រពៃណីជាតិ"},
        {"label": datetime(year, 4, 15).strftime('%Y-%m-%d'),
         "value": "ពិធីបុណ្យចូលឆ្នាំថ្មីប្រពៃណីជាតិ"},
        {"label": datetime(year, 4, 16).strftime('%Y-%m-%d'),
         "value": "ពិធីបុណ្យចូលឆ្នាំថ្មីប្រពៃណីជាតិ"},
        {"label": datetime(year, 5, 1).strftime('%Y-%m-%d'),
         "value": "ទិវាពលកម្មអន្តរជាតិ"},
        {"label": datetime(year, 5, 14).strftime(
            '%Y-%m-%d'), "value": "ព្រះរាជពិធីបុណ្យចម្រើនព្រះជន្ម ព្រះករុណា ព្រះបាទសម្តេចព្រះបរមនាថ នរោត្តម សីហមុនី"},
        {"label": datetime(year, 5, 15).strftime(
            '%Y-%m-%d'), "value": "ព្រះរាជពិធីច្រត់ព្រះនង្គ័ល"},
        {"label": datetime(year, 6, 18).strftime(
            '%Y-%m-%d'), "value": "ព្រះរាជពិធីបុណ្យចម្រើនព្រះជន្ម សម្តេចព្រះមហាក្សត្រី ព្រះវររាជមាតា នរោត្តម មុនិនាថ​ សីហនុ"},
        {"label": datetime(year, 9, 24).strftime('%Y-%m-%d'),
         "value": "ទិវាប្រកាសរដ្ឋធម្មនុញ្ញ"},
        {"label": datetime(year, 9, 21).strftime('%Y-%m-%d'),
         "value": "ពិធីបុណ្យភ្ផុំបិណ្ឌ"},
        {"label": datetime(year, 9, 22).strftime('%Y-%m-%d'),
         "value": "ពិធីបុណ្យភ្ផុំបិណ្ឌ"},
        {"label": datetime(year, 9, 23).strftime('%Y-%m-%d'),
         "value": "ពិធីបុណ្យភ្ផុំបិណ្ឌ"},
        {"label": datetime(year, 10, 15).strftime(
            '%Y-%m-%d'), "value": "ទិវាប្រារព្ឋពិធីគោរពព្រះវិញ្ញាណក្ខន្ឋ ព្រះករុណា ព្រះបាទសម្តេចព្រះ នរោត្តម សីហនុ ព្រះមហាវីរក្សត្រ ព្រះវររាជបិតាឯករាជ្យ បូរណភាពទឹកដី និងឯកភាពជាតិខ្មែរ  'ព្រះបរមរតនកោដ្ឋ'"},
        {"label": datetime(year, 10, 29).strftime(
            '%Y-%m-%d'), "value": "ព្រះរាជពិធីគ្រងព្រះបរមរាជសម្បត្តិ របស់ ព្រះករុណា ព្រះបាទសម្តេចព្រះបរមនាថ នរោត្តម សីហមុនី ព្រះមហាក្សត្រនៃព្រះរាជាណាចក្រកម្ពុជា"},
        {"label": datetime(year, 11, 9).strftime('%Y-%m-%d'),
         "value": "ពិធីបុណ្យឯករាជ្យជាតិ"},
        {"label": datetime(year, 11, 4).strftime(
            '%Y-%m-%d'), "value": "ព្រះរាជពិធីបុណ្យអុំទូក បណ្តែតប្រទីប និងសំពះព្រះខែអកអំបុក"},
        {"label": datetime(year, 11, 5).strftime(
            '%Y-%m-%d'), "value": "ព្រះរាជពិធីបុណ្យអុំទូក បណ្តែតប្រទីប និងសំពះព្រះខែអកអំបុក"},
        {"label": datetime(year, 11, 6).strftime(
            '%Y-%m-%d'), "value": "ព្រះរាជពិធីបុណ្យអុំទូក បណ្តែតប្រទីប និងសំពះព្រះខែអកអំបុក"},
        {"label": datetime(year, 12, 29).strftime(
            '%Y-%m-%d'), "value": "ទិវាសន្តិភាពនៅកម្ពុជា"},

    ]
    return holidays
