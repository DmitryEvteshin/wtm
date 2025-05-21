declare namespace frontend {
    /** Склад */
    export type IStock = {
        id: number
        name: string
        tasks_count: number
    }

    /** Задача для списка */
    export type ITaskL = {
        material: string
        material_id: number
        doc_id: number
        doc_number: string
        planned_date: string
        technical_process: string
        operation: string
        amount: number
        weight: number|string
        amount_fact: number
        weight_fact: number
        tare_type: string
        category: string
        net_weight_fact: number
        done: number
    }

    /** Задание из задачи */
    export type IJob = {
        /** id материала */
        material_id: string
        /** название материала */
        material: string
        /** id тары */
        tare_id: number
        /** маркировка */
        tare_mark: string
        /** вес тары */
        tara_weight: number
        /** брутто */
        rest_gross_weight: number
        /** категория */
        category: string
        /** тип тары */
        tare_type: string
        /** кол-во тар */
        task_tare_amount: number
        /** нетто */
        task_net_weight: number
        /** взято веса нетто */
        net_weight_fact: number
        /** id типа процесса */
        add_processing_id: number
        /** работа выполнена */
        done: boolean
    }

    /** Ограничение по весу в категории материала */
    export type ITaskWeight = {
        category: string
        net_weight_fact: number
        material: string
        material_id: number
        tare_amount: number
        tare_amount_fact: number
        task_weight: number
        category_details: string
    }

    export type IProcessingType = {
        id: number
        process_name: string
    }

    export type ICatMat = {
        [key: string]: string
    }

    /** Задача со списком заданий */
    export type ITaskP = {
        id: number
        doc_number: string
        doc_date: string
        planned_date: string
        stock: number
        technical_process: string
        operation: string
        material: string
        task_weights: Array<ITaskWeight>
        jobs: Array<IJob>
        processing_types: Array<IProcessingType>
        catmat: ICatMat
    }

    export type ILoginPayload = {
        login: string;
        password: string;
    }

    export type IChangePassword = {
        newPassword: string;
        repetitionPassword: string;
    }

    export type IDocList = {
        next_doc_number_list: string;
    }


}
