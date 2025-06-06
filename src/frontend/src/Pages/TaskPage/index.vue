<template>
    <el-row v-loading="store.loading">
        <el-col v-if="store.task">
            <MetaInfo
                :meta-info="metaInfo"
                :doc-number="store.task.doc_number"
                :material="store.task.material">
                <FiltersJobs
                    v-model:selected-statuses="selectedStatuses"
                    v-model:selected-categorits="selectedCategorits"
                    :categories-options="categoriesOptions" />
            </MetaInfo>
            <StatInfo :stat-info="statInfo">
                <div
                    style="text-align: end; width: 100%;"
                    class="mb">
                    <div>
                        <el-button
                            type="success"
                            icon="Edit"
                            plain
                            :disabled="checkAllCount.done === 0"
                            @click="checkAll(true)">
                            отметить все [ {{ checkAllCount.done.toLocaleString() }} ]
                        </el-button>
                        <el-button
                            type="warning"
                            icon="Edit"
                            plain
                            :disabled="checkAllCount.progress === 0"
                            @click="checkAll(false)">
                            снять все [ {{ checkAllCount.progress.toLocaleString() }} ]
                        </el-button>
                    </div>
                </div>
            </StatInfo>
            <JobsTable
                :jobs-list="computedJobsData"
                :processing-types="store.task.processing_types"
                :is-landscape="store.isLandscape"
                @change-status="updateJobStatus"
                @processing-change="processingChange"
                @change-r-g-w="onChangeRGW" />
        </el-col>
    </el-row>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, computed, ref } from "vue";
import { useRouter } from "vue-router";
import useApplicationStore from "@/store";
import { ElMessage, ElMessageBox } from "element-plus";
import dayjs from "dayjs";
import MetaInfo from "./MetaInfo.vue";
import StatInfo from "./StatInfo.vue";
import FiltersJobs from "./FiltersJobs.vue";
import JobsTable from "./JobsTable.vue";

const props = defineProps({
    /** ID склада */
    stockID: { type: Number, required: true },
    /** ID задачи */
    taskID: { type: Number, required: true },
    /** ID материала */
    materialID: { type: Number, required: true }
});
const router = useRouter();
const store = useApplicationStore();
const searchParams = new URLSearchParams(location.search);
const queryParams = {
    /** Тип тары */
    tareType: searchParams.get("tareType") ?? "",
    /** Категория материала в задаче */
    categoryTask: searchParams.get("categoryTask")??""
};
/**
 * 1) Получение данных задачи
 * 2) Запуск автообновления
 */
onMounted(async () => {
    if (isNaN(props.taskID)) await router.push("/");
    await store.fetchTask(props.stockID, props.taskID, props.materialID, queryParams.tareType);
    await store.doAutofetch(props.stockID, props.taskID, props.materialID, queryParams.tareType);
});
/**
 * Остановка автообновления
 */
onBeforeUnmount(() => {
    store.task = null;
    store.stopAutofetch();
});
const processingChange = () => store.stopAutofetch();
/** Запрос к API на обновление статуса задания */
const updateJobStatus = async (job: frontend.IJob, weight: number) => {
    try {
        const realNetWeightFact = weight - job.tara_weight;
        const realRestGrossWeight = job.rest_gross_weight == weight ? 0 : job.rest_gross_weight - realNetWeightFact 
        const alertWeight = job.net_weight_fact > 0 ? (remainingWeight.value[job.category] + (job.net_weight_fact-realNetWeightFact)) : (remainingWeight.value[job.category] - realNetWeightFact);
        const newStatus = !job.done;

        if (newStatus === false) {
            const check_item = await store.checkMaterialItem(props.materialID, job.tare_id, props.taskID);
            if (check_item[0].next_doc_number_list != "") {
                const message = `Невозможно отменить выполнение. Позиция ${job.tare_id} передана в производство (${check_item[0].next_doc_number_list})`    
                ElMessageBox.alert(message, "Предупреждение", { confirmButtonText: "OK" })
                return;
            }
        }

        if (newStatus === true && alertWeight < 0) {
            try {
                await ElMessageBox.confirm(
                    "Предупреждение",
                    {
                        message: `Превышение веса (нетто) на ${alertWeight*-1}`,
                        confirmButtonText: "Подтверждение",
                        cancelButtonText: "Отмена",
                        type: "warning"
                    }
                );
            } catch (error) {
                // eslint-disable-next-line
                console.warn(error);
                return;
            }
        }
        await store.updateJobStatus(props.taskID, props.materialID, job.tare_id, realNetWeightFact, realRestGrossWeight, job.add_processing_id, newStatus);
        await store.fetchTask(props.stockID, props.taskID, props.materialID, queryParams.tareType);
        const readebleStatus = newStatus === true ? "готово" : "не выполнено";
        const message = `Тара с маркировкой "${job.tare_mark}" (тара ${job.tare_id}) - статус изменен на "${readebleStatus}"`;
        ElMessage({
            showClose: false,
            message: message,
            type: newStatus ? "success" : "warning"
        });
    } catch (error) {
        alert(error);
    }
};
/** Функция для подсчета кол-ва заданий по статусу */
const sumJobsStatus = (jobs: Array<frontend.IJob>, status: boolean, category: string) => {
    return jobs.reduce((prev, job) => prev = job.done === status && job.category === category ? prev + 1 : prev, 0);
};
/** Вычисляемое свойство (обертка для таблицы) - метаданные задачи */
const metaInfo = computed(() => ({
    fields: [
        {
            label: "Материал",
            prop: "material",
            width: 150
        },
        {
            label: "Техпроцесс",
            prop: "technical_process",
            width: 220
        },
        {
            label: "Операция",
            prop: "operation",
            width: 150
        },
        {
            label: "Плановая дата",
            prop: "planned_date",
            width: 150
        }
    ],
    data: [
        {
            material: store.task?.material,
            technical_process: store.task?.technical_process,
            operation: store.task?.operation,
            tareType: queryParams.tareType,
            planned_date: dayjs(store.task?.planned_date as string, "YYYY-MM-DD").format("DD.MM.YYYY")
        }
    ]
}));

/** Вычисляемое свойство (обертка для таблицы) - статистика заданий */
const statInfo = computed(() => {
    const findTaskWeight = (category: string) => {
        const catWeightstore = store.task?.task_weights.find(tw => tw.category === category);
        if (catWeightstore) {
            return catWeightstore.task_weight;
        }
        return store.task?.jobs.reduce((prev,cur) => cur.category === category ? prev+=cur.task_net_weight : prev, 0)??0;
    };
    const sumNetWeightComplited = (category: string) => {
        return store.task?.task_weights.find(tw => tw.category === category)?.net_weight_fact?? store.task?.jobs.reduce((prev,cur) => cur.done && cur.category === category ? prev+=cur.net_weight_fact : prev, 0)??0;
    };
    return categoriesOptions.value.map(category => ({
        categoryLabel: category,
        catmat: store.task?.catmat[category]?.split(";")?? [],
        data: [
            {
                label: "Задание",
                count: store.task?.jobs.reduce((prev,cur) => cur.category === category ? prev+=1 : prev, 0),
                netWeight: findTaskWeight(category)
            },
            {
                label: "Выполнено",
                count: store.task?.jobs ? sumJobsStatus(store.task.jobs as frontend.IJob[], true, category) : 0,
                netWeight: sumNetWeightComplited(category)
            },
            {
                label: "Осталось",
                count: store.task?.jobs ? sumJobsStatus(store.task.jobs as frontend.IJob[], false, category) : 0,
                netWeight: findTaskWeight(category) - sumNetWeightComplited(category)
            }
        ]
    }));
});

const onChangeRGW = (job: frontend.IJob) => {
    store.updateRestGrossWeight(props.taskID, job).then(() => {
        store.fetchTask(props.stockID, props.taskID, props.materialID, queryParams.tareType);
    }).catch(reason => {
        alert(reason);
    });
};

/** Остатки веса по категориям */
const remainingWeight = computed(() => {
    const remainings: {[key: string]: number} = {};
    statInfo.value.forEach(si => {
        remainings[si.categoryLabel] = si.data[2]?.netWeight??0;
    });
    return remainings;
});

/** фильтр по статусам */
const selectedStatuses = ref<number>(0);
/** фильтр по категории */
const selectedCategorits = ref<string[]>([]);


const categoriesOptions = computed(() => Array.from(new Set<string>(store.task?.jobs.map(job => job.category === "" ? "" : job.category))).sort());
/** Список работ для таблицы с учетом фильтров */
const computedJobsData = computed<frontend.IJob[]>(() => {
    const jobs = (store.task?.jobs ?? []).filter(j => {
        switch (selectedStatuses.value) {
            case 1:
                return j.done === true;
            case 2:
                return j.done === false;
            default:
                return true;
        }
    });
    return selectedCategorits.value.length ? jobs.filter(j => selectedCategorits.value.includes(j.category)) : jobs;
});

const checkAllCount = computed(() => {
    const jobs = store.task?.jobs;
    if (!jobs) {
        return {
            done: 0,
            progress: 0
        };;
    }
    const doneCount = jobs.reduce((prev: number, j: frontend.IJob) => {
        return j.done === true ? prev : prev+1;
    }, 0);
    return {
        done: doneCount,
        progress: (jobs.length - doneCount)
    };
});

const checkAll = async (status: boolean) => {
    const jobs: frontend.IJob[] = store.task?.jobs ?? [];
    if (!jobs.length) {
        return;
    }
    try {
        const tasksCount = status === true ? checkAllCount.value.done : checkAllCount.value.progress;
        const alertText = status === true ? "завершенные" : "не завершенные" ;
        await ElMessageBox.confirm(
            "Предупреждение",
            {
                message: `Это действие затронет позиции: ${tasksCount}. Отметить их как "${alertText}"?`,
                confirmButtonText: "Подтвердить",
                cancelButtonText: "Отмена",
                type: "warning"
            }
        );
    } catch (error) {
        // eslint-disable-next-line
                console.warn(error);
        return;
    }
    const checkAllParams = {
        taskID: props.taskID,
        materialID: props.materialID,
        jobs: jobs.filter(job => job.done !== status).map(job => ({
            tara_id: job.tare_id,
            add_processing_id: job.add_processing_id,
            net_weight_fact: status === true ? job.rest_gross_weight - job.tara_weight : 0,
            rest_gross_weight: 0,
            status: status
        }))
    };
    await store.updateJobsStatus(checkAllParams);
    await store.fetchTask(props.stockID, props.taskID, props.materialID, queryParams.tareType);
};
</script>
