
Welcome back.

Last lesson we kicked things off with checking how smart our models are against some basic tests like

accuracy or F1 scores.

And we painted it as the model's first test drive, seeing if it gets the basics right.

But real life is more messy.

The data out there is always more complex and unpredictable than what we test on, so just passing these

initial tests is usually not enough.

We talked about the gaps, how test data can't capture everything and might even carry some biases.

And now we've arrived at eight different dimensions of model performance.

So let's jump right in.

The first one is robustness.

This refers to how well the model performs under varying conditions or when faced with unexpected or

noisy data.

This is important because in the real world, it is no longer a question of if your model will encounter

such data, and we need to be prepared to handle it.

A robust model maintains its performance even in the face of adversarial examples or data that significantly

deviates from the training set.

Such edge cases can be ignored.

They need to be handled and the model needs to be stress test for it to be actually ready for deployment.

All right.

The second one is generalizability.

Generalizability is the model's ability to perform well on new, unseen data, not just the data it

was trained on.

If you have created your test and evaluation datasets correctly, your model might still have found

a way to cheat, shortcut, or learn just enough to do well on those sets of data.

And as we have talked earlier, the training and testing data set will almost always be incomplete and

imperfect.

A model that generalizes well avoids overfitting to the training data and can adapt to a variety of

situations.

This is a quality we definitely want for our production ready model that will surely encounter all different

kinds of weird and unexpected data inputs.

Okay.

The third one is about a widespread problem in machine learning, and one that is especially important

in some industries.

That is fairness and bias, ensuring that the model does not perpetuate or exacerbate biases present

in the training data is crucial, especially in applications that affect people's lives.

This includes being fair across the different groups and not discriminating based on race, gender,

age, or other such factors.

A model that is fair and unbiased should also aspire to keep parity between inequalities that actually

are real and present in the real world, and avoid adopting existing biased views.

Okay.

Before going further, it is important to note how there is no textbook way of solving such problems

in our models.

A step by step process that perfectly solves these issues all the time doesn't exist.

Instead, it is always an iterative process that oftentimes requires creativity, domain knowledge,

and a dose of trial and error.

However, this is also one of the steps that makes the biggest difference and allows models that could

only live in a lab, get out there in the real world, and actually become useful.

This is the trait that separates the exceptional machine learning engineers and AI companies from the

rest.

Okay with that out of the way, an increasingly important aspect to consider, especially for models

used in critical decision making processes, is its interpretability and explainability.

This refers to the ability to understand and explain how and why a model makes its predictions.

This includes being able to trace back the decision making process and also understand the models patterns,

as well as its limitations.

This is still a big area of research and explainability works much worse for some architectures than

for others.

However, you should still consider doing the most you can with your model and consider integrating

some sort of tracing or auditing mechanism into your pipeline right from the start.

All right.

And since we've been talking about taking the model from the lab and into the real world, it might

also naturally have to deal with compliance and ethical considerations.

This means ensuring that the model complies with legal and ethical standards, especially regarding

data privacy, security, and usage rights.

If your model is at risk of breaking such standards, this might very well be the most important step

to go through before deploying your model.

All right.

Before going into the last three aspects, let's talk a bit about the other important performance perspective

for our models.

Speed.

When we talk about deploying models, particularly for applications that demand real time responses,

the speed at which a model processes and delivers predictions, known as its inference speed, is naturally

very important.

This isn't merely about the accuracy of the outcomes.

It is equally about the velocity at which these results are provided.

The crux of the matter is that the right answer delayed, is oftentimes a missed opportunity, and that

is especially true in scenarios where decisions need to be made fast.

So how do we measure this speed performance?

We will have a dedicated section later in the course, where we will thoroughly examine different performance

strategies, as well as the economic perspectives and trade offs for them.

But for now, let's briefly overview two critical dimensions of speed performance that you will want

to consider for your model.

Okay, so firstly your model can be quick here.

The emphasis is on the model's responsiveness combined with a low latency.

Latency refers to the duration taken for a model to return a single prediction from the moment the query

is made in real time applications such as autonomous driving or fraud detection.

Low latency is non-negotiable.

That is because these applications hinge on the model's ability to process and deliver insights instantaneously.

We will explore various techniques to minimize latency, ensuring our model is not simply accurate but

also agile.

Okay.

On the flip side, there is throughput.

The model's capacity to process a high volume of tasks over a given period.

High throughput is about maximizing the number of predictions our model can deliver within a set time

frame.

This is particularly relevant in scenarios like batch processing, in data analytics, or for handling

large scale user interactions in web services.

We'll examine how to enhance throughput, optimizing the model for handling high volume tasks efficiently,

thereby achieving an optimal balance between speed and cost per inference.

Both latency and throughput are critical, but they cater to different needs.

The art lies in understanding the unique requirements of our application and fine tuning our machine

learning system speed and performance accordingly.

We will have a comprehensive section later in the course, where I'll guide you through selecting the

right strategy for your model and use case, ensuring it not only functions optimally, but also aligns

perfectly with the specific temporal demands of its intended application.

All right.

It's time to continue with the last three fundamental aspects of performance.

And then our overview on balancing speed and accuracy.

We will continue this in the next lesson.

I'll see you there.